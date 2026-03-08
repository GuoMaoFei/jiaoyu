"""
Reporter Tools - Tools for the Reporter Agent to query and aggregate learning analytics.
"""
from typing import Optional
from langchain_core.tools import tool
from sqlalchemy import select, func, case

from app.database import AsyncSessionLocal
from app.models.user import StudentNodeState
from app.models.material import KnowledgeNode
from app.models.testing import StudentMistake, MistakeStatus
from app.models.chat import ChatAssessment


@tool
async def get_chapter_health_report(student_id: str, material_id: str) -> str:
    """
    Get a chapter-level aggregated health report for a student on a specific material.
    Groups knowledge nodes by their top-level parent (chapter) and calculates average health scores.
    
    Args:
        student_id: The student's unique ID.
        material_id: The material/textbook ID.
    
    Returns:
        A formatted chapter-level health summary with traffic light indicators.
    """
    async with AsyncSessionLocal() as db:
        # Get all nodes for this material
        nodes_result = await db.execute(
            select(KnowledgeNode)
            .where(KnowledgeNode.material_id == material_id)
            .order_by(KnowledgeNode.level, KnowledgeNode.seq_num)
        )
        all_nodes = nodes_result.scalars().all()
        
        if not all_nodes:
            return f"教材 {material_id} 暂无知识树节点。"
        
        # Build parent-child mapping to find top-level chapters
        node_map = {n.id: n for n in all_nodes}
        chapters = [n for n in all_nodes if n.level == 1]
        
        def get_descendants(parent_id):
            """Get all descendant node IDs recursively."""
            children = [n.id for n in all_nodes if n.parent_id == parent_id]
            desc = list(children)
            for c in children:
                desc.extend(get_descendants(c))
            return desc
        
        # Get student's node states
        states_result = await db.execute(
            select(StudentNodeState).where(
                StudentNodeState.student_id == student_id
            )
        )
        states = {s.node_id: s for s in states_result.scalars().all()}
        
        # Build chapter report
        output = [f"# 学情概览报告\n\n学生ID: {student_id}\n"]
        
        for ch in chapters:
            descendant_ids = [ch.id] + get_descendants(ch.id)
            scores = []
            for nid in descendant_ids:
                if nid in states:
                    scores.append(states[nid].health_score)
            
            if scores:
                avg = sum(scores) / len(scores)
                coverage = len(scores) / len(descendant_ids) * 100
            else:
                avg = 0
                coverage = 0
            
            # Traffic light
            if avg >= 80:
                light = "🟢"
            elif avg >= 50:
                light = "🟡"
            else:
                light = "🔴"
            
            output.append(
                f"{light} **{ch.title}** — 平均健康度: {avg:.0f}/100, "
                f"覆盖率: {coverage:.0f}% ({len(scores)}/{len(descendant_ids)} 节点)"
            )
        
        return "\n".join(output)


@tool
async def get_mistake_summary(student_id: str, limit: int = 10) -> str:
    """
    Get a summary of the student's recent mistakes, grouped by knowledge node.
    
    Args:
        student_id: The student's unique ID.
        limit: Maximum number of mistakes to return.
    
    Returns:
        A formatted summary of recent mistakes with their status.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(StudentMistake)
            .where(
                StudentMistake.student_id == student_id,
                StudentMistake.status != MistakeStatus.MASTERED
            )
            .order_by(StudentMistake.created_at.desc())
            .limit(limit)
        )
        mistakes = result.scalars().all()
        
        if not mistakes:
            return "该学生暂无未掌握的错题记录。表现良好！"
        
        output = [f"# 错题摘要（共 {len(mistakes)} 条未掌握）\n"]
        
        for i, m in enumerate(mistakes, 1):
            # Get node title
            node_result = await db.execute(
                select(KnowledgeNode.title).where(KnowledgeNode.id == m.node_id)
            )
            node_title = node_result.scalar() or "Unknown"
            
            status_icon = {"NEW": "🆕", "REVIEWING": "🔄", "MASTERED": "✅"}.get(
                m.status.value, "❓"
            )
            
            output.append(
                f"{i}. {status_icon} 【{node_title}】\n"
                f"   错因: {m.error_reason or '未分析'}\n"
                f"   连续做对次数: {m.consecutive_correct_count}"
            )
        
        return "\n".join(output)
