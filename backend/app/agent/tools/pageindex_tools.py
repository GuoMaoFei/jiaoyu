import json
from typing import List, Optional, Dict, Any
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.database import AsyncSessionLocal
from app.models.material import KnowledgeNode, KnowledgeContent
from app.utils.llm_router import get_fast_model


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
        # 1. Fetch current node and its context
        current_node = None
        if current_node_id:
            stmt_cur = select(KnowledgeNode).where(KnowledgeNode.id == current_node_id)
            res_cur = await db.execute(stmt_cur)
            current_node = res_cur.scalars().first()

        if not current_node:
            # Fallback to just getting the first node to at least have a context base if seq_num logic is needed
            stmt_fallback = (
                select(KnowledgeNode)
                .where(KnowledgeNode.material_id == material_id)
                .order_by(KnowledgeNode.seq_num)
            )
            res_fallback = await db.execute(stmt_fallback)
            current_node = res_fallback.scalars().first()

        if not current_node:
            return "No curriculum context found for this material."

        # 2. Build the History + Current Context Pool
        # We want nodes in the same material that are logically equal or before the current node
        stmt_pool = (
            select(KnowledgeNode)
            .where(
                KnowledgeNode.material_id == material_id,
                KnowledgeNode.seq_num <= current_node.seq_num,
            )
            .order_by(KnowledgeNode.seq_num)
        )
        res_pool = await db.execute(stmt_pool)
        historical_nodes = res_pool.scalars().all()

        # Aggregate the JSON summaries
        candidate_pool = []
        for node in historical_nodes:
            if node.pi_nodes_json:
                # Append chapter context to each PI node summary for better LLM routing
                for pi_node in node.pi_nodes_json:
                    candidate_pool.append(
                        {
                            "chapter_title": node.title,
                            "pi_node_id": pi_node.get("node_id"),
                            "summary": pi_node.get("summary", ""),
                            "title": pi_node.get("title", ""),
                        }
                    )

        if not candidate_pool:
            return "No structured knowledge index found for this material."

        # 3. LLM Node Reasoning (Routing)
        # We use a fast LLM to pick the best PI Node IDs out of the pool
        pool_json_str = json.dumps(candidate_pool, ensure_ascii=False)

        router_prompt = f"""
        You are an expert librarian and tutor routing agent.
        A student is studying and has a question. To answer it correctly without hallucinating, 
        you must select the most relevant knowledge nodes from the curriculum's index.
        
        Student's Question: {query}
        Historical Weaknesses (Focus on these if relevant): {expert_preference}
        
        Here is the catalog of currently available knowledge chunks (Current Chapter + Past Chapters):
        {pool_json_str}
        
        Analyze the student's question and select a MAXIMUM OF 3 `pi_node_id`s from the catalog above 
        that contain the necessary information to answer the question.
        Output your selection as a JSON array of strings containing ONLY the selected `pi_node_id`s.
        If none are relevant, output an empty array [].
        """

        router_llm = get_fast_model()
        structured_router = router_llm.with_structured_output(
            schema={
                "type": "object",
                "properties": {
                    "selected_pi_ids": {"type": "array", "items": {"type": "string"}}
                },
            },
            method="json_mode",
        )

        try:
            from langchain_core.messages import SystemMessage

            route_res = await structured_router.ainvoke(
                [SystemMessage(content=router_prompt)]
            )

            if isinstance(route_res, list):
                selected_ids = route_res
            elif isinstance(route_res, dict):
                selected_ids = route_res.get("selected_pi_ids", [])
            else:
                selected_ids = []
        except Exception as e:
            print(f"[ERROR] LLM Router failed parsing: {e}")
            selected_ids = []

        if not selected_ids:
            return "No highly relevant detailed curriculum content found for this specific query. Please try to answer generally based on the current chapter title."

        # 4. Content Fetching (Go to KnowledgeContent table to get the heavy text)
        stmt_fetch = select(KnowledgeContent).where(
            KnowledgeContent.knowledge_node_id.in_([n.id for n in historical_nodes]),
            KnowledgeContent.pi_node_id.in_(selected_ids),
        )
        res_fetch = await db.execute(stmt_fetch)
        contents = res_fetch.scalars().all()

        if not contents:
            return (
                "The selected nodes did not contain valid text content in the database."
            )

        output = ["--- RETRIEVED CURRICULUM CONTEXT ---"]
        for c in contents:
            parent_title = next(
                (n.title for n in historical_nodes if n.id == c.knowledge_node_id),
                "Unknown Chapter",
            )
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
    """
    Factory function to create a state-bound search tool.
    This is now a wrapper around the static tool for cleaner sub-agent injection.
    """

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
