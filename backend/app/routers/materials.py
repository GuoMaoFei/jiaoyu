"""
Materials Router - Handles textbook/material CRUD and knowledge tree operations.
"""

import logging
import os
import asyncio
import shutil
from pathlib import Path
import json
from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db, async_session_factory
from app.models.material import Material, MaterialType, KnowledgeNode, KnowledgeContent
from app.schemas.materials import (
    MaterialCreateRequest,
    MaterialResponse,
    MaterialListResponse,
    TreeBuildRequest,
    TreeBuildResponse,
    KnowledgeTreeResponse,
    KnowledgeNodeResponse,
    KnowledgePointBrief,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/materials", tags=["Materials"])

ALLOWED_EXTENSIONS = {".pdf"}
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


_processing_tasks: Dict[str, dict] = {}


def _update_task(material_id: str, status: TaskStatus, **kwargs):
    entry = _processing_tasks.get(material_id, {})
    entry.update({"status": status.value, "updated_at": datetime.now().isoformat(), **kwargs})
    _processing_tasks[material_id] = entry


class _TaskLogger:
    """Collects log lines for a background task and writes to file."""

    def __init__(self, material_id: str, pdf_path: str):
        self.material_id = material_id
        self.lines: List[str] = []
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_name = os.path.basename(pdf_path)
        self.log_path = LOGS_DIR / f"{material_id}_{pdf_name}_{ts}.log"

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.lines.append(line)
        logger.info(f"[BuildTree:{self.material_id[:8]}] {msg}")

    def flush(self):
        self.log_path.write_text("\n".join(self.lines), encoding="utf-8")


async def _run_build_tree(material_id: str, pdf_path: str):
    """Background task: build knowledge tree with its own DB session."""
    task_log = _TaskLogger(material_id, pdf_path)
    _update_task(material_id, TaskStatus.PROCESSING, log_file=str(task_log.log_path))

    task_log.log(f"开始处理: {os.path.basename(pdf_path)}")
    try:
        async with async_session_factory() as db:
            from app.services.tree_builder import TreeBuilderService
            builder = TreeBuilderService(db_session=db)

            task_log.log("加载 PDF 并检查缓存...")
            result = await builder.ingest_material(
                material_id=material_id, pdf_url_or_path=pdf_path
            )

            # 知识点提取（独立 try/except，失败不影响树构建状态）
            try:
                from app.services.kp_extractor import KnowledgePointExtractor
                kp_extractor = KnowledgePointExtractor(db)
                kp_stats = await kp_extractor.extract_for_material(material_id)
                await db.commit()
                task_log.log(f"知识点提取完成: {kp_stats}")
                try:
                    from app.agent.tools.kp_tools import invalidate_kp_candidate_cache
                    invalidate_kp_candidate_cache()
                except Exception:
                    pass
            except Exception as e:
                task_log.log(f"知识点提取失败（不影响树构建）: {e}")
                await db.rollback()

            await db.commit()

            node_count = result.get("node_count", 0) if isinstance(result, dict) else "?"
            task_log.log(f"处理完成! doc_id={result.get('doc_id', '?')}")
            _update_task(material_id, TaskStatus.COMPLETED, result=result)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        task_log.log(f"处理失败: {e}\n{tb}")
        _update_task(material_id, TaskStatus.FAILED, error=str(e))
    finally:
        task_log.flush()
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except Exception:
                pass


def validate_upload_file(file: UploadFile) -> None:
    """Validate uploaded file for security."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    filename = file.filename.lower()
    ext = os.path.splitext(filename)[1]

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    if ".." in file.filename or "/" in file.filename or "\\" in file.filename:
        raise HTTPException(status_code=400, detail="Invalid filename")


@router.post("/", response_model=MaterialResponse)
async def create_material(
    request: MaterialCreateRequest, db: AsyncSession = Depends(get_db)
):
    """Register a new textbook/material in the system."""
    material = Material(
        title=request.title,
        grade=request.grade,
        subject=request.subject,
        version=request.version,
        publisher=request.publisher,
        material_type=MaterialType.OFFICIAL,
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)

    return MaterialResponse(
        id=material.id,
        title=material.title,
        grade=material.grade,
        subject=material.subject,
        version=material.version,
        publisher=material.publisher,
        material_type=material.material_type.value,
        created_at=material.created_at,
        node_count=0,
    )


@router.get("/", response_model=MaterialListResponse)
async def list_materials(
    grade: Optional[str] = None,
    subject: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List all available materials with pagination."""
    offset = (page - 1) * page_size

    stmt = select(Material)
    if grade:
        stmt = stmt.where(Material.grade == grade)
    if subject:
        stmt = stmt.where(Material.subject == subject)

    count_stmt = select(func.count(Material.id))
    if grade:
        count_stmt = count_stmt.where(Material.grade == grade)
    if subject:
        count_stmt = count_stmt.where(Material.subject == subject)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(Material.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    materials = result.scalars().all()

    if not materials:
        return MaterialListResponse(materials=[], total=total)

    material_ids = [m.id for m in materials]
    node_count_stmt = (
        select(
            KnowledgeNode.material_id,
            func.count(KnowledgeNode.id).label("node_count"),
        )
        .where(KnowledgeNode.material_id.in_(material_ids))
        .group_by(KnowledgeNode.material_id)
    )
    node_count_result = await db.execute(node_count_stmt)
    node_counts = {row.material_id: row.node_count for row in node_count_result}

    material_list = [
        MaterialResponse(
            id=m.id,
            title=m.title,
            grade=m.grade,
            subject=m.subject,
            version=m.version,
            publisher=m.publisher,
            material_type=m.material_type.value,
            created_at=m.created_at,
            node_count=node_counts.get(m.id, 0),
        )
        for m in materials
    ]

    return MaterialListResponse(materials=material_list, total=total)


@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(material_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single material by ID."""
    result = await db.execute(select(Material).where(Material.id == material_id))
    material = result.scalars().first()

    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    count_result = await db.execute(
        select(func.count(KnowledgeNode.id)).where(
            KnowledgeNode.material_id == material.id
        )
    )
    node_count = count_result.scalar() or 0

    return MaterialResponse(
        id=material.id,
        title=material.title,
        grade=material.grade,
        subject=material.subject,
        version=material.version,
        publisher=material.publisher,
        material_type=material.material_type.value,
        created_at=material.created_at,
        node_count=node_count,
    )


@router.get("/{material_id}/tree", response_model=KnowledgeTreeResponse)
async def get_knowledge_tree(material_id: str, db: AsyncSession = Depends(get_db)):
    """Get the full knowledge tree for a material."""
    # Verify material exists
    result = await db.execute(select(Material).where(Material.id == material_id))
    material = result.scalars().first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    # Get all nodes
    nodes_result = await db.execute(
        select(KnowledgeNode)
        .where(KnowledgeNode.material_id == material_id)
        .order_by(KnowledgeNode.level, KnowledgeNode.seq_num)
    )
    nodes = nodes_result.scalars().all()

    # Count children for each node
    node_children_count = {}
    for n in nodes:
        parent = n.parent_id
        if parent:
            node_children_count[parent] = node_children_count.get(parent, 0) + 1

    def _get_preview(n):
        """Extract a content preview from pi_nodes_json or title."""
        if (
            n.pi_nodes_json
            and isinstance(n.pi_nodes_json, list)
            and len(n.pi_nodes_json) > 0
        ):
            first_summary = n.pi_nodes_json[0].get("summary", "")
            if first_summary:
                return first_summary[:200]
        return None

    # Batch load knowledge points for all nodes
    node_ids = [n.id for n in nodes]
    kp_by_node: Dict[str, List[KnowledgePointBrief]] = {nid: [] for nid in node_ids}
    if node_ids:
        from app.models.knowledge_point import KnowledgePointMapping, KnowledgePoint
        kp_stmt = (
            select(KnowledgePointMapping.knowledge_node_id, KnowledgePoint.id, KnowledgePoint.title, KnowledgePoint.level)
            .join(KnowledgePoint, KnowledgePointMapping.knowledge_point_id == KnowledgePoint.id)
            .where(KnowledgePointMapping.knowledge_node_id.in_(node_ids))
        )
        kp_result = await db.execute(kp_stmt)
        for row in kp_result.all():
            kp_by_node[str(row.knowledge_node_id)].append(
                KnowledgePointBrief(id=str(row.id), title=row.title, level=row.level)
            )

    node_list = [
        KnowledgeNodeResponse(
            id=n.id,
            title=n.title,
            level=n.level,
            seq_num=n.seq_num,
            parent_id=n.parent_id,
            content_preview=_get_preview(n),
            children_count=node_children_count.get(n.id, 0),
            knowledge_points=kp_by_node.get(n.id) or None,
        )
        for n in nodes
    ]

    return KnowledgeTreeResponse(
        material_id=material_id,
        material_title=material.title,
        nodes=node_list,
        total_nodes=len(node_list),
    )


@router.get("/{material_id}/knowledge-points")
async def get_material_knowledge_points(material_id: str, db: AsyncSession = Depends(get_db)):
    """Return knowledge points associated with a material (via KnowledgeNode mappings)."""
    result = await db.execute(select(Material).where(Material.id == material_id))
    material = result.scalars().first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    from app.models.knowledge_point import KnowledgePoint, KnowledgePointMapping

    stmt = (
        select(KnowledgePoint)
        .join(KnowledgePointMapping, KnowledgePoint.id == KnowledgePointMapping.knowledge_point_id)
        .join(KnowledgeNode, KnowledgePointMapping.knowledge_node_id == KnowledgeNode.id)
        .where(KnowledgeNode.material_id == material_id)
        .distinct()
    )
    res = await db.execute(stmt)
    points = res.scalars().all()

    return {
        "material_id": material_id,
        "knowledge_points": [
            {
                "id": p.id,
                "title": p.title,
                "summary": p.summary,
                "keywords": p.keywords,
                "level": p.level,
                "source_count": p.source_count,
            }
            for p in points
        ],
    }


@router.get("/knowledge-points/tree")
async def get_subject_knowledge_tree(subject: str, db: AsyncSession = Depends(get_db)):
    """Return the knowledge-point tree for a given subject."""
    from app.models.knowledge_point import KnowledgePoint

    result = await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.subject == subject)
    )
    points = result.scalars().all()

    # Build id -> node dict
    point_map = {p.id: p for p in points}
    children_map: Dict[str, List[dict]] = {}
    for p in points:
        parent = p.parent_id or ""
        children_map.setdefault(parent, []).append({
            "id": p.id,
            "title": p.title,
            "summary": p.summary,
            "keywords": p.keywords,
            "level": p.level,
            "source_count": p.source_count,
            "children": [],
        })

    # Attach children recursively
    def attach_children(node: dict) -> None:
        node["children"] = children_map.get(node["id"], [])
        for child in node["children"]:
            attach_children(child)

    # Root nodes (parent_id is None or empty)
    roots = children_map.get("", [])
    # Also handle cases where parent_id refers to a non-existent node
    orphan_ids = set(point_map.keys())
    for r in roots:
        orphan_ids.discard(r["id"])
    for nid in list(orphan_ids):
        p = point_map[nid]
        if p.parent_id and p.parent_id not in point_map:
            roots.append({
                "id": p.id,
                "title": p.title,
                "summary": p.summary,
                "keywords": p.keywords,
                "level": p.level,
                "source_count": p.source_count,
                "children": [],
            })

    for r in roots:
        attach_children(r)

    return {
        "subject": subject,
        "total_points": len(points),
        "tree": roots,
    }


@router.post("/build-tree", response_model=TreeBuildResponse)
async def build_knowledge_tree(
    request: TreeBuildRequest, db: AsyncSession = Depends(get_db)
):
    """
    Trigger knowledge tree construction from a PDF via PageIndex.
    This is a synchronous call that waits for completion.
    For production, consider using BackgroundTasks.
    """
    from app.services.tree_builder import TreeBuilderService

    try:
        builder = TreeBuilderService(db_session=db)
        result = await builder.ingest_material(
            material_id=request.material_id, pdf_url_or_path=request.pdf_url
        )

        # 知识点提取（独立 try/except，失败不影响树构建状态）
        try:
            from app.services.kp_extractor import KnowledgePointExtractor
            kp_extractor = KnowledgePointExtractor(db)
            kp_stats = await kp_extractor.extract_for_material(request.material_id)
            await db.commit()
            logger.info(f"[KP_EXTRACT] material={request.material_id} stats={kp_stats}")
            try:
                from app.agent.tools.kp_tools import invalidate_kp_candidate_cache
                invalidate_kp_candidate_cache()
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"[KP_EXTRACT] material={request.material_id} extraction failed: {e}")

        return TreeBuildResponse(
            status=result["status"],
            message=result["message"],
            doc_id=result.get("doc_id"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImportError as e:
        raise HTTPException(
            status_code=503, detail=f"PageIndex SDK not available: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"Tree build failed: {e}")
        raise HTTPException(status_code=500, detail=f"Tree build failed: {str(e)}")


@router.post("/{material_id}/upload")
async def upload_material_pdf(
    material_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    """Upload a PDF for a material and start building its knowledge tree in the background."""
    validate_upload_file(file)

    content_length = file.headers.get("content-length")
    if content_length and int(content_length) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    result = await db.execute(select(Material).where(Material.id == material_id))
    material = result.scalars().first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    current = _processing_tasks.get(material_id, {})
    if current.get("status") in (TaskStatus.PENDING.value, TaskStatus.PROCESSING.value):
        raise HTTPException(status_code=409, detail="该教材正在处理中，请稍后查看状态")

    os.makedirs("uploads", exist_ok=True)

    safe_filename = os.path.basename(file.filename)
    temp_file_path = os.path.join("uploads", f"{material_id}_{safe_filename}")

    total_size = 0
    with open(temp_file_path, "wb") as buffer:
        for chunk in iter(lambda: file.file.read(1024 * 1024), b""):
            total_size += len(chunk)
            if total_size > MAX_FILE_SIZE:
                buffer.close()
                os.remove(temp_file_path)
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
                )
            buffer.write(chunk)

    _update_task(material_id, TaskStatus.PENDING)
    asyncio.create_task(_run_build_tree(material_id, temp_file_path))

    return {"status": "processing", "message": "PDF 已上传，知识树正在后台构建中"}


@router.get("/{material_id}/status")
async def get_material_status(material_id: str):
    """Get the current processing status for a material's knowledge tree build."""
    task = _processing_tasks.get(material_id)
    if not task:
        return {"status": "none", "message": "无处理任务"}

    resp = dict(task)

    log_file = task.get("log_file")
    if log_file and os.path.exists(log_file):
        try:
            content = Path(log_file).read_text(encoding="utf-8")
            resp["log_tail"] = content[-2000:] if len(content) > 2000 else content
        except Exception:
            pass

    return resp


@router.delete("/{material_id}")
async def delete_material(material_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a material and all related data (knowledge tree, cache, activations, etc.)."""
    result = await db.execute(select(Material).where(Material.id == material_id))
    material = result.scalars().first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    # Get all node IDs for this material (needed for cleaning up non-cascaded references)
    nodes_result = await db.execute(
        select(KnowledgeNode.id).where(KnowledgeNode.material_id == material_id)
    )
    node_ids = [row[0] for row in nodes_result.all()]

    # --- Knowledge Point cleanup (before deleting nodes) ---
    try:
        from app.services.kp_extractor import KnowledgePointExtractor
        kp_extractor = KnowledgePointExtractor(db)
        kp_cleanup_result = await kp_extractor.cleanup_for_material(material_id)
        logger.info(f"[KP_CLEANUP] material={material_id} result={kp_cleanup_result}")
    except Exception as e:
        logger.warning(f"[KP_CLEANUP] material={material_id} cleanup failed: {e}")

    if node_ids:
        from app.models.chat import ChatSession, ChatAssessment
        from app.models.user import StudentNodeState, BookActivation
        from app.models.lesson import LessonProgress, PlanItem
        from app.models.quiz import NodeQuiz
        from app.models.testing import StudentMistake
        from app.models.material import Question

        # Delete records that reference knowledge_nodes but lack cascade
        for model_cls, fk_col in [
            (ChatAssessment, ChatAssessment.node_id),
            (ChatSession, ChatSession.node_id),
            (StudentNodeState, StudentNodeState.node_id),
            (StudentMistake, StudentMistake.node_id),
            (LessonProgress, LessonProgress.node_id),
            (PlanItem, PlanItem.node_id),
            (NodeQuiz, NodeQuiz.node_id),
            (Question, Question.node_id),
        ]:
            await db.execute(
                model_cls.__table__.delete().where(fk_col.in_(node_ids))
            )

    # BookActivation references materials directly
    from app.models.user import BookActivation
    await db.execute(
        BookActivation.__table__.delete().where(BookActivation.material_id == material_id)
    )

    # Delete the material (cascade handles KnowledgeNode -> KnowledgeContent)
    await db.delete(material)
    await db.commit()

    from app.agent.tools.pageindex_tools import invalidate_candidate_cache
    invalidate_candidate_cache(material_id)

    # Invalidate KP candidate cache (subject-scoped)
    try:
        from app.agent.tools.kp_tools import invalidate_kp_candidate_cache
        invalidate_kp_candidate_cache(material.subject)
    except Exception:
        pass

    # Clean up OCR cache files
    cache_dir = Path("cache/page_cache") / f"{material_id}_pages_cache"
    if cache_dir.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)
        logger.info(f"Deleted OCR cache for material {material_id}")

    # Clean up tree/TOC cache files
    for cache_name in [f"{material_id}_tree_structure.json", f"{material_id}_toc_cache.json"]:
        cache_file = Path("cache/page_cache") / cache_name
        if cache_file.exists():
            cache_file.unlink()

    logger.info(f"Deleted material {material_id}: {material.title}")
    return {"status": "ok", "message": f"Material '{material.title}' deleted successfully"}


@router.delete("/{material_id}/cache", status_code=204)
async def clear_material_cache(material_id: str, db: AsyncSession = Depends(get_db)):
    """Clear OCR cache for a material when it's activated."""
    from app.agent.tools.pageindex_tools import invalidate_candidate_cache
    invalidate_candidate_cache(material_id)
    try:
        result = await db.execute(select(Material).where(Material.id == material_id))
        material = result.scalars().first()
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        # Use hash to find cache files
        import hashlib

        # Get all cache files for this material
        cache_dir = Path("cache/page_cache")
        if not cache_dir.exists():
            return None

        # Find cache files by searching for ones containing the material_id in filename
        files_deleted = 0
        for cache_file in cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                files_deleted += 1
            except Exception:
                pass

        # Also clear per-page cache directory
        pages_cache_dir = cache_dir / f"{material_id}_pages_cache"
        if pages_cache_dir.exists():
            for f in pages_cache_dir.glob("*"):
                f.unlink()
                files_deleted += 1
            pages_cache_dir.rmdir()

        # Clear new unified text cache directory
        text_cache_dir = Path("cache/text_cache") / material_id
        if text_cache_dir.exists():
            for f in text_cache_dir.glob("*"):
                f.unlink()
                files_deleted += 1
            text_cache_dir.rmdir()

        logger.info(f"Deleted {files_deleted} cache files for material {material_id}")
        return None

    except Exception as e:
        logger.exception(f"Failed to clear cache for material {material_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")
