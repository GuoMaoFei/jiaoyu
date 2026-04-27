"""
Knowledge Points Router - REST API for knowledge point tree operations.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.knowledge_point import KnowledgePoint, KnowledgePointMapping
from app.models.material import KnowledgeNode, KnowledgeContent, Material
from app.schemas.knowledge_points import (
    KnowledgePointNodeResponse,
    KnowledgePointTreeResponse,
    KnowledgePointDetailResponse,
    KnowledgePointMappingResponse,
    KnowledgePointSearchResponse,
    KnowledgePointSearchResultItem,
    KnowledgePointMaterialsResponse,
    KnowledgePointMaterialItem,
)
from app.agent.tools.candidate_filter import prefilter_candidates, rank_candidates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge-points", tags=["KnowledgePoints"])


@router.get("/subjects/{subject}/tree", response_model=KnowledgePointTreeResponse)
async def get_knowledge_point_tree(
    subject: str, db: AsyncSession = Depends(get_db)
):
    """获取某学科的知识点树"""
    result = await db.execute(
        select(KnowledgePoint)
        .where(KnowledgePoint.subject == subject)
        .order_by(KnowledgePoint.level, KnowledgePoint.title)
    )
    all_points = result.scalars().all()

    if not all_points:
        return KnowledgePointTreeResponse(subject=subject, total_points=0, tree=[])

    # 构建树
    id_to_node: dict = {}
    for kp in all_points:
        node = KnowledgePointNodeResponse(
            id=kp.id,
            title=kp.title,
            summary=kp.summary,
            keywords=kp.keywords,
            level=kp.level,
            source_count=kp.source_count,
            children=[],
        )
        id_to_node[kp.id] = node

    roots = []
    for kp in all_points:
        node = id_to_node[kp.id]
        if kp.parent_id and kp.parent_id in id_to_node:
            id_to_node[kp.parent_id].children.append(node)
        else:
            roots.append(node)

    # 清理空 children
    def _clean_empty(node: KnowledgePointNodeResponse):
        if node.children is not None and len(node.children) == 0:
            node.children = None
        elif node.children:
            for child in node.children:
                _clean_empty(child)

    for root in roots:
        _clean_empty(root)

    return KnowledgePointTreeResponse(
        subject=subject,
        total_points=len(all_points),
        tree=roots,
    )


@router.get("/{kp_id}", response_model=KnowledgePointDetailResponse)
async def get_knowledge_point_detail(
    kp_id: str, db: AsyncSession = Depends(get_db)
):
    """获取知识点详情"""
    result = await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.id == kp_id)
    )
    kp = result.scalar_one_or_none()
    if not kp:
        raise HTTPException(status_code=404, detail="Knowledge point not found")

    # 查询映射
    mappings_result = await db.execute(
        select(KnowledgePointMapping, KnowledgeNode, Material)
        .join(KnowledgeNode, KnowledgePointMapping.knowledge_node_id == KnowledgeNode.id)
        .join(Material, KnowledgeNode.material_id == Material.id)
        .where(KnowledgePointMapping.knowledge_point_id == kp_id)
    )
    mappings = mappings_result.all()

    mapping_responses = []
    for mapping, node, material in mappings:
        mapping_responses.append(KnowledgePointMappingResponse(
            knowledge_node_id=node.id,
            knowledge_node_title=node.title,
            material_id=material.id,
            material_title=material.title,
            relevance_score=mapping.relevance_score,
            context_snippet=mapping.context_snippet,
        ))

    return KnowledgePointDetailResponse(
        id=kp.id,
        title=kp.title,
        summary=kp.summary,
        keywords=kp.keywords,
        level=kp.level,
        subject=kp.subject,
        source_count=kp.source_count,
        parent_id=kp.parent_id,
        mappings=mapping_responses,
    )


@router.get("/subjects/{subject}/search", response_model=KnowledgePointSearchResponse)
async def search_knowledge_points_api(
    subject: str,
    q: str = Query(..., description="搜索查询"),
    top_k: int = Query(5, description="返回数量"),
    db: AsyncSession = Depends(get_db),
):
    """搜索知识点"""
    result = await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.subject == subject)
    )
    all_points = result.scalars().all()

    if not all_points:
        return KnowledgePointSearchResponse(subject=subject, query=q, results=[])

    # 构建候选池
    candidate_pool = []
    nodes_map = {}
    for kp in all_points:
        candidate_pool.append({
            "knowledge_point_id": str(kp.id),
            "title": kp.title,
            "summary": kp.summary or "",
            "keywords": kp.keywords or "",
            "parent_id": str(kp.parent_id) if kp.parent_id else None,
            "level": kp.level,
            "source_count": kp.source_count,
            "knowledge_node_id": str(kp.id),
        })
        nodes_map[str(kp.id)] = kp

    # bigram 预过滤 + 排序
    filtered = prefilter_candidates(q, candidate_pool, top_k=20)
    selected = rank_candidates(q, filtered, top_k=top_k, nodes_map=nodes_map)

    results = []
    for item in selected:
        kp_id = item.get("knowledge_point_id")
        kp = nodes_map.get(kp_id)
        if kp:
            results.append(KnowledgePointSearchResultItem(
                id=kp.id,
                title=kp.title,
                summary=kp.summary,
                level=kp.level,
                source_count=kp.source_count,
            ))

    return KnowledgePointSearchResponse(subject=subject, query=q, results=results)


@router.get("/{kp_id}/materials", response_model=KnowledgePointMaterialsResponse)
async def get_knowledge_point_materials(
    kp_id: str, db: AsyncSession = Depends(get_db)
):
    """获取知识点关联的教材"""
    result = await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.id == kp_id)
    )
    kp = result.scalar_one_or_none()
    if not kp:
        raise HTTPException(status_code=404, detail="Knowledge point not found")

    # 查询映射 → KnowledgeNode → Material
    mappings_result = await db.execute(
        select(KnowledgePointMapping, KnowledgeNode, Material)
        .join(KnowledgeNode, KnowledgePointMapping.knowledge_node_id == KnowledgeNode.id)
        .join(Material, KnowledgeNode.material_id == Material.id)
        .where(KnowledgePointMapping.knowledge_point_id == kp_id)
    )
    mappings = mappings_result.all()

    material_items = []
    for mapping, node, material in mappings:
        # 获取内容预览
        content_result = await db.execute(
            select(KnowledgeContent.content_md)
            .where(KnowledgeContent.knowledge_node_id == node.id)
            .limit(1)
        )
        content_row = content_result.first()
        content_preview = content_row[0][:200] if content_row and content_row[0] else None

        material_items.append(KnowledgePointMaterialItem(
            material_id=material.id,
            material_title=material.title,
            node_title=node.title,
            content_preview=content_preview,
        ))

    return KnowledgePointMaterialsResponse(
        knowledge_point_id=kp.id,
        knowledge_point_title=kp.title,
        materials=material_items,
    )
