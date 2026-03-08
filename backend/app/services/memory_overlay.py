"""
Memory Overlay Service
Queries the database for a student's learning profile and returns a structured
summary that can be injected into Agent prompts as "Expert Preference".

This replaces the hard-coded mock data that was previously in supervisor_node.
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import AsyncSessionLocal
from app.models.user import StudentNodeState
from app.models.testing import StudentMistake, MistakeStatus
from app.models.material import KnowledgeNode


async def get_student_memory_overlay(
    student_id: str,
    material_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Query the student's learning profile from the database.
    
    Returns a dict containing:
    - avg_health_score: Average health score across all nodes for this student
    - weak_nodes: List of nodes with health_score < 60
    - historical_mistakes_summary: A text summary of recent active mistakes
    - weakest_node_id: The id of the weakest node (for Assessor targeting)
    """
    async with AsyncSessionLocal() as db:
        # 1. Query StudentNodeState for health scores
        stmt = select(StudentNodeState).where(
            StudentNodeState.student_id == student_id
        )
        result = await db.execute(stmt)
        node_states = result.scalars().all()
        
        if not node_states:
            # No learning history — return defaults
            return {
                "avg_health_score": 50,
                "weak_nodes": [],
                "historical_mistakes_summary": "暂无学习记录，这是该生的第一次学习。",
                "weakest_node_id": "unknown"
            }
        
        # Calculate average health score
        scores = [ns.health_score for ns in node_states]
        avg_score = sum(scores) // len(scores) if scores else 50
        
        # Find weak nodes (health_score < 60)
        weak_states = [ns for ns in node_states if ns.health_score < 60]
        weak_node_ids = [ns.node_id for ns in weak_states]
        
        # Find the weakest one
        weakest = min(node_states, key=lambda ns: ns.health_score)
        
        # 2. Query active mistakes for this student
        mistake_stmt = (
            select(StudentMistake)
            .where(
                StudentMistake.student_id == student_id,
                StudentMistake.status != MistakeStatus.MASTERED
            )
            .order_by(StudentMistake.updated_at.desc())
            .limit(5)
        )
        mistake_result = await db.execute(mistake_stmt)
        recent_mistakes = mistake_result.scalars().all()
        
        # 3. Build the mistakes summary text
        if recent_mistakes:
            mistake_lines = []
            for m in recent_mistakes:
                reason = m.error_reason or "原因待诊断"
                mistake_lines.append(f"- 节点{m.node_id}: {reason}")
            mistakes_summary = "该生近期薄弱点：\n" + "\n".join(mistake_lines)
        else:
            # No explicit mistakes, but might have weak nodes
            if weak_states:
                weak_lines = [f"- 节点{ns.node_id}: 健康度 {ns.health_score}/100" for ns in weak_states[:5]]
                mistakes_summary = "该生以下知识点掌握薄弱：\n" + "\n".join(weak_lines)
            else:
                mistakes_summary = "该生目前学习状态良好，暂无明显薄弱点。"
        
        # 4. Optionally get node titles for richer context
        if weak_node_ids:
            title_stmt = select(KnowledgeNode.id, KnowledgeNode.title).where(
                KnowledgeNode.id.in_(weak_node_ids[:5])
            )
            title_result = await db.execute(title_stmt)
            node_titles = {row.id: row.title for row in title_result}
            
            # Enrich mistake summary with node titles
            enriched_lines = []
            for ns in weak_states[:5]:
                title = node_titles.get(ns.node_id, ns.node_id)
                enriched_lines.append(f"- 「{title}」: 健康度 {ns.health_score}/100")
            if enriched_lines:
                mistakes_summary = "该生以下知识点掌握薄弱：\n" + "\n".join(enriched_lines)
        
        return {
            "avg_health_score": avg_score,
            "weak_nodes": weak_node_ids,
            "historical_mistakes_summary": mistakes_summary,
            "weakest_node_id": weakest.node_id
        }
