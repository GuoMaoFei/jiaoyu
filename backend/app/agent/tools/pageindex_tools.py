import time
from typing import List, Optional, Dict, Any, Tuple

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import AsyncSessionLocal
from app.models.material import KnowledgeNode, KnowledgeContent
from app.models.user import BookActivation
from app.agent.tools.candidate_filter import prefilter_candidates, rank_candidates

_candidate_pool_cache: Dict[str, Tuple[float, List[Dict], Dict[str, Any]]] = {}
_CACHE_TTL = 600


def invalidate_candidate_cache(material_id: str = None):
    if material_id:
        _candidate_pool_cache.pop(material_id, None)
    else:
        _candidate_pool_cache.clear()


async def _get_candidate_pool(material_id: str, db: AsyncSession) -> Tuple[List[Dict], Dict[str, Any]]:
    now = time.time()

    if material_id in _candidate_pool_cache:
        cached_time, cached_pool, cached_nodes_map = _candidate_pool_cache[material_id]
        if now - cached_time < _CACHE_TTL:
            print(f"[CACHE HIT] candidate pool for material {material_id}: {len(cached_pool)} items")
            return cached_pool, cached_nodes_map

    stmt_pool = (
        select(KnowledgeNode)
        .where(KnowledgeNode.material_id == material_id)
        .order_by(KnowledgeNode.seq_num)
    )
    res_pool = await db.execute(stmt_pool)
    all_nodes = res_pool.scalars().all()

    nodes_map = {str(n.id): n for n in all_nodes}

    candidate_pool = []
    for node in all_nodes:
        if node.pi_nodes_json:
            for pi_node in node.pi_nodes_json:
                summary = pi_node.get("summary", "")
                if not summary:
                    continue
                candidate_pool.append({
                    "chapter_title": node.title,
                    "pi_node_id": pi_node.get("node_id"),
                    "summary": summary,
                    "title": pi_node.get("title", ""),
                    "knowledge_node_id": str(node.id),
                    "level": node.level,
                    "parent_id": str(node.parent_id) if node.parent_id else None,
                })

    _candidate_pool_cache[material_id] = (now, candidate_pool, nodes_map)
    print(f"[CACHE MISS] built candidate pool for material {material_id}: {len(candidate_pool)} items")
    return candidate_pool, nodes_map


class SearchKnowledgeParams(BaseModel):
    query: str = Field(description="The student's question or the topic to search for.")
    material_id: str = Field(description="The ID of the textbook/material.")
    student_id: str = Field(description="The student's unique ID.")
    current_node_id: Optional[str] = Field(
        None,
        description="The ID of the current knowledge node the student is studying.",
    )
    expert_preference: str = Field(
        "", description="Any historical mistakes or weak points to focus the search."
    )


@tool(args_schema=SearchKnowledgeParams)
async def search_knowledge_tree(
    query: str,
    material_id: str,
    student_id: str,
    current_node_id: Optional[str] = None,
    expert_preference: str = "",
) -> str:
    """
    Search the standard curriculum knowledge tree for a specific material.
    Use this tool BEFORE answering any student questions to ensure you do not hallucinate knowledge outside the curriculum.
    This tool intelligently searches across the student's current learning context and previously learned chapters.
    """
    async with AsyncSessionLocal() as db:
        # Verify student has activated this material
        activation_stmt = select(BookActivation).where(
            BookActivation.student_id == student_id,
            BookActivation.material_id == material_id,
        )
        activation_res = await db.execute(activation_stmt)
        if not activation_res.scalars().first():
            return f"Student has not activated material {material_id}. Please activate the textbook first."

        candidate_pool, nodes_map = await _get_candidate_pool(material_id, db)

        if not candidate_pool:
            return "No structured knowledge index found for this material."

        SELECT_K = 3
        PREFILTER_K = 20

        filtered = prefilter_candidates(query, candidate_pool, top_k=PREFILTER_K)
        print(f"[SEARCH] bigram prefilter: {len(candidate_pool)} -> {len(filtered)}")

        if not filtered:
            filtered = candidate_pool[:PREFILTER_K]
            print(f"[SEARCH] no bigram matches, fallback to first {len(filtered)}")

        selected = rank_candidates(
            query,
            filtered,
            top_k=SELECT_K,
            current_node_id=current_node_id,
            nodes_map=nodes_map,
        )
        selected_ids = [c["pi_node_id"] for c in selected]
        print(f"[SEARCH] tree+bigram ranked, selected: {selected_ids}")

        if not selected_ids:
            return "No highly relevant detailed curriculum content found for this specific query. Please try to answer generally based on the current chapter title."

        knowledge_node_ids = set()
        for c in candidate_pool:
            if c["pi_node_id"] in selected_ids:
                knowledge_node_ids.add(c["knowledge_node_id"])

        stmt_fetch = select(KnowledgeContent).where(
            KnowledgeContent.knowledge_node_id.in_(knowledge_node_ids),
            KnowledgeContent.pi_node_id.in_(selected_ids),
        )
        res_fetch = await db.execute(stmt_fetch)
        contents = res_fetch.scalars().all()

        if not contents:
            return "The selected nodes did not contain valid text content in the database."

        output = ["--- RETRIEVED CURRICULUM CONTEXT ---"]
        node_title_map = {str(n.id): n.title for n in nodes_map.values()}
        for c in contents:
            parent_title = node_title_map.get(c.knowledge_node_id, "Unknown Chapter")
            output.append(f"\n[{parent_title} (ID: {c.pi_node_id})]:\n{c.content_md}")

        return "\n".join(output)


class NodeSelectionParams(BaseModel):
    query: str = Field(description="The student's question or the topic to search for.")


def create_search_knowledge_tree_tool(
    student_id: str,
    material_id: str,
    current_node_id: Optional[str] = None,
    expert_preference: str = "",
):
    @tool(args_schema=NodeSelectionParams)
    async def dynamic_search_knowledge_tree(query: str) -> str:
        """
        Search the standard curriculum knowledge tree for a specific material.
        Used by Tutor Agent with pre-bound context.
        """
        return await search_knowledge_tree.ainvoke(
            {
                "query": query,
                "material_id": material_id,
                "student_id": student_id,
                "current_node_id": current_node_id,
                "expert_preference": expert_preference,
            }
        )

    return dynamic_search_knowledge_tree
