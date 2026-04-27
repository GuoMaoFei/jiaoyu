"""
跨教材知识点搜索工具：search_knowledge_points
按学科搜索知识点树，通过映射表关联多本教材内容。
"""
import time
import logging
from typing import List, Optional, Dict, Any, Tuple

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import AsyncSessionLocal
from app.models.knowledge_point import KnowledgePoint, KnowledgePointMapping
from app.models.material import KnowledgeNode, KnowledgeContent, Material
from app.models.user import BookActivation
from app.agent.tools.candidate_filter import prefilter_candidates, rank_candidates

logger = logging.getLogger(__name__)

# ── 知识点候选池缓存 ────────────────────────────────────────────

_kp_candidate_pool_cache: Dict[str, Tuple[float, List[Dict], Dict[str, Any]]] = {}
_KP_CACHE_TTL = 600


def invalidate_kp_candidate_cache(subject: str = None):
    """失效知识点候选池缓存"""
    if subject:
        _kp_candidate_pool_cache.pop(subject, None)
    else:
        _kp_candidate_pool_cache.clear()


async def _get_kp_candidate_pool(
    subject: str, db: AsyncSession
) -> Tuple[List[Dict], Dict[str, Any]]:
    """获取知识点候选池（带缓存）"""
    now = time.time()

    if subject in _kp_candidate_pool_cache:
        cached_time, cached_pool, cached_map = _kp_candidate_pool_cache[subject]
        if now - cached_time < _KP_CACHE_TTL:
            logger.debug(f"[KP_CACHE HIT] subject={subject} pool_size={len(cached_pool)}")
            return cached_pool, cached_map

    # 查询该学科所有知识点
    result = await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.subject == subject)
    )
    all_points = result.scalars().all()

    # 构建 nodes_map（用于树近邻计算）
    nodes_map = {str(p.id): p for p in all_points}

    # 构建候选池
    candidate_pool = []
    for kp in all_points:
        candidate_pool.append({
            "knowledge_point_id": str(kp.id),
            "title": kp.title,
            "summary": kp.summary or "",
            "keywords": kp.keywords or "",
            "parent_id": str(kp.parent_id) if kp.parent_id else None,
            "level": kp.level,
            "source_count": kp.source_count,
            # 兼容 candidate_filter 的字段名
            "knowledge_node_id": str(kp.id),
        })

    _kp_candidate_pool_cache[subject] = (now, candidate_pool, nodes_map)
    logger.info(f"[KP_CACHE MISS] built pool for subject={subject}: {len(candidate_pool)} items")
    return candidate_pool, nodes_map


# ── 搜索工具 ────────────────────────────────────────────────────

class SearchKnowledgePointsParams(BaseModel):
    query: str = Field(description="学生的提问或要搜索的主题")
    subject: str = Field(description="学科名称，如'数学'、'物理'")
    student_id: str = Field(description="学生 ID")


@tool(args_schema=SearchKnowledgePointsParams)
async def search_knowledge_points(
    query: str,
    subject: str,
    student_id: str,
) -> str:
    """
    跨教材搜索知识点：按学科搜索知识点树，返回学生已激活教材中的相关内容。
    当学生的问题涉及其他章节或其他教材的概念时使用此工具。
    """
    async with AsyncSessionLocal() as db:
        # 1. 获取知识点候选池
        candidate_pool, nodes_map = await _get_kp_candidate_pool(subject, db)

        if not candidate_pool:
            return f"学科 '{subject}' 暂无知识点索引。"

        # 2. bigram 预过滤 top 20
        PREFILTER_K = 20
        filtered = prefilter_candidates(query, candidate_pool, top_k=PREFILTER_K)
        logger.info(f"[KP_SEARCH] subject={subject} query='{query}' candidates={len(candidate_pool)} prefiltered={len(filtered)}")

        if not filtered:
            filtered = candidate_pool[:PREFILTER_K]

        # 3. 树近邻加分 + bigram 精细排序 top 5
        SELECT_K = 5
        selected = rank_candidates(
            query,
            filtered,
            top_k=SELECT_K,
            current_node_id=None,
            nodes_map=nodes_map,
        )
        selected_kp_ids = [c["knowledge_point_id"] for c in selected]
        logger.info(f"[KP_SEARCH] selected {len(selected)} knowledge points: {selected_kp_ids}")

        if not selected_kp_ids:
            return "未找到与查询高度相关的知识点。"

        # 4. 查询学生已激活的教材
        activations_result = await db.execute(
            select(BookActivation.material_id).where(
                BookActivation.student_id == student_id
            )
        )
        activated_material_ids = set(row[0] for row in activations_result.all())

        # 5. 通过 Mapping → KnowledgeNode → KnowledgeContent 取回原文
        # 一次性 JOIN 查询映射、节点、教材
        mappings_result = await db.execute(
            select(KnowledgePointMapping, KnowledgePoint, KnowledgeNode, Material)
            .join(KnowledgePoint, KnowledgePointMapping.knowledge_point_id == KnowledgePoint.id)
            .join(KnowledgeNode, KnowledgePointMapping.knowledge_node_id == KnowledgeNode.id)
            .join(Material, KnowledgeNode.material_id == Material.id)
            .where(KnowledgePointMapping.knowledge_point_id.in_(selected_kp_ids))
        )
        mappings = mappings_result.all()

        if not mappings:
            return "找到知识点但无关联教材内容。"

        # 过滤已激活教材并收集 node_id
        node_ids_to_fetch = set()
        mapping_data = []  # (kp_title, node_id, material_id, node_title)
        for mapping_row, kp_row, node_row, mat_row in mappings:
            if mat_row.id not in activated_material_ids:
                continue
            node_ids_to_fetch.add(node_row.id)
            mapping_data.append((kp_row.title, node_row.id, mat_row.id, node_row.title))

        if not mapping_data:
            return "找到知识点但学生未激活相关教材。"

        # 查询 KnowledgeContent
        contents_result = await db.execute(
            select(KnowledgeContent).where(
                KnowledgeContent.knowledge_node_id.in_(node_ids_to_fetch)
            )
        )
        contents = contents_result.scalars().all()
        content_by_node = {}
        for c in contents:
            content_by_node.setdefault(c.knowledge_node_id, []).append(c.content_md)

        # Material 标题已在 JOIN 中获取
        material_title_map = {mat_row.id: mat_row.title for _mr, _kp, _kn, mat_row in mappings}

        # 6. 格式化输出
        output = ["--- RETRIEVED KNOWLEDGE POINT CONTEXT ---"]
        seen = set()
        for kp_title, node_id, mat_id, node_title in mapping_data:
            key = (kp_title, node_id)
            if key in seen:
                continue
            seen.add(key)
            mat_title = material_title_map.get(mat_id, "未知教材")
            content_texts = content_by_node.get(node_id, [])
            content_str = "\n".join(content_texts)[:2000] if content_texts else "（无内容）"
            output.append(f"\n[{kp_title} (来源: {mat_title} - {node_title})]:\n{content_str}")

        return "\n".join(output)


# ── 动态绑定工厂 ────────────────────────────────────────────────

class KPSearchParams(BaseModel):
    query: str = Field(description="学生的提问或要搜索的主题")


def create_search_knowledge_points_tool(
    student_id: str,
    subject: str,
    current_kp_id: Optional[str] = None,
):
    """创建预绑定上下文的知识点搜索工具实例"""
    @tool(args_schema=KPSearchParams)
    async def dynamic_search_knowledge_points(query: str) -> str:
        """
        跨教材搜索知识点：按学科搜索知识点树，返回学生已激活教材中的相关内容。
        当学生的问题涉及其他章节或其他教材的概念时使用此工具。
        """
        return await search_knowledge_points.ainvoke({
            "query": query,
            "subject": subject,
            "student_id": student_id,
        })

    return dynamic_search_knowledge_points
