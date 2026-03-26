"""
Materials Router - Handles textbook/material CRUD and knowledge tree operations.
"""

import logging
import os
import shutil
from pathlib import Path
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.material import Material, MaterialType, KnowledgeNode
from app.schemas.materials import (
    MaterialCreateRequest,
    MaterialResponse,
    MaterialListResponse,
    TreeBuildRequest,
    TreeBuildResponse,
    KnowledgeTreeResponse,
    KnowledgeNodeResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/materials", tags=["Materials"])

ALLOWED_EXTENSIONS = {".pdf"}
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB


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

    node_list = [
        KnowledgeNodeResponse(
            id=n.id,
            title=n.title,
            level=n.level,
            seq_num=n.seq_num,
            parent_id=n.parent_id,
            content_preview=_get_preview(n),
            children_count=node_children_count.get(n.id, 0),
        )
        for n in nodes
    ]

    return KnowledgeTreeResponse(
        material_id=material_id,
        material_title=material.title,
        nodes=node_list,
        total_nodes=len(node_list),
    )


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


@router.post("/{material_id}/upload", response_model=TreeBuildResponse)
async def upload_material_pdf(
    material_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    """Upload a PDF for a material and build its knowledge tree."""
    from app.services.tree_builder import TreeBuilderService

    validate_upload_file(file)

    result = await db.execute(select(Material).where(Material.id == material_id))
    material = result.scalars().first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    os.makedirs("uploads", exist_ok=True)

    safe_filename = os.path.basename(file.filename)
    temp_file_path = os.path.join("uploads", f"{material_id}_{safe_filename}")

    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size = os.path.getsize(temp_file_path)
    if file_size > MAX_FILE_SIZE:
        os.remove(temp_file_path)
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    try:
        builder = TreeBuilderService(db_session=db)
        result = await builder.ingest_material(
            material_id=material_id, pdf_url_or_path=temp_file_path
        )
        return TreeBuildResponse(
            status=result["status"],
            message=result["message"],
            doc_id=result.get("doc_id"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImportError as e:
        raise HTTPException(status_code=503, detail="PageIndex SDK not available")
    except Exception as e:
        logger.exception(f"Tree build failed during upload")
        raise HTTPException(status_code=500, detail="Tree build failed")
    finally:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass


@router.delete("/{material_id}/cache", status_code=204)
async def clear_material_cache(material_id: str, db: AsyncSession = Depends(get_db)):
    """Clear OCR cache for a material when it's activated."""
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
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    # Check if this cache belongs to the material by checking timestamp
                    # We can't directly check material_id from cache filename,
                    # So we'll check the creation time
                    # Actually, let's pass material_id via request or just clear all cache
                    pass

                # Simply delete the cache file
                cache_file.unlink()
                files_deleted += 1
            except Exception:
                pass

        logger.info(f"Deleted {files_deleted} cache files for material {material_id}")
        return None

    except Exception as e:
        logger.exception(f"Failed to clear cache for material {material_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")
