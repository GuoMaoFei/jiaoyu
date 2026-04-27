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
from app.models.user import StudentNodeState, BookActivation
from app.models.testing import StudentMistake, MistakeStatus
from app.models.material import KnowledgeNode, Material


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
    - weak_knowledge_points: List of weak knowledge points (跨教材聚合)
    - cross_material_suggestions: List of cross-material suggestions
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
                "weakest_node_id": "unknown",
                "weak_knowledge_points": [],
                "cross_material_suggestions": [],
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
        
        # 5. Knowledge point dimension analysis (跨教材薄弱分析)
        weak_knowledge_points = []
        cross_material_suggestions = []
        
        try:
            from app.models.knowledge_point import KnowledgePoint, KnowledgePointMapping
            
            # 查询有 knowledge_point_id 的错题，按知识点分组
            kp_mistake_stmt = (
                select(
                    StudentMistake.knowledge_point_id,
                    func.count(StudentMistake.id).label("mistake_count")
                )
                .where(
                    StudentMistake.student_id == student_id,
                    StudentMistake.knowledge_point_id.isnot(None),
                    StudentMistake.status != MistakeStatus.MASTERED
                )
                .group_by(StudentMistake.knowledge_point_id)
                .order_by(func.count(StudentMistake.id).desc())
            )
            kp_mistake_result = await db.execute(kp_mistake_stmt)
            kp_mistake_rows = kp_mistake_result.all()
            
            # 筛选 mistake_count >= 2 的知识点
            weak_kp_ids = []
            for row in kp_mistake_rows:
                if row.mistake_count >= 2:
                    weak_kp_ids.append(row.knowledge_point_id)
            
            if weak_kp_ids:
                # 查询知识点详情
                kp_result = await db.execute(
                    select(KnowledgePoint).where(KnowledgePoint.id.in_(weak_kp_ids))
                )
                weak_kps = kp_result.scalars().all()
                
                for kp in weak_kps:
                    weak_knowledge_points.append({
                        "id": kp.id,
                        "title": kp.title,
                        "mistake_count": next(
                            (r.mistake_count for r in kp_mistake_rows if r.knowledge_point_id == kp.id), 0
                        ),
                        "subject": kp.subject,
                    })
                
                # 跨教材推荐：对每个薄弱知识点查询其他已激活教材中的映射
                activations_result = await db.execute(
                    select(BookActivation.material_id).where(
                        BookActivation.student_id == student_id
                    )
                )
                activated_material_ids = set(row[0] for row in activations_result.all())
                
                for kp in weak_kps:
                    mapping_result = await db.execute(
                        select(KnowledgePointMapping, KnowledgeNode, Material)
                        .join(KnowledgeNode, KnowledgePointMapping.knowledge_node_id == KnowledgeNode.id)
                        .join(Material, KnowledgeNode.material_id == Material.id)
                        .where(KnowledgePointMapping.knowledge_point_id == kp.id)
                    )
                    mappings = mapping_result.all()
                    
                    for mapping, node, mat in mappings:
                        # 排除当前教材，仅保留已激活教材
                        if material_id and mat.id == material_id:
                            continue
                        if mat.id not in activated_material_ids:
                            continue
                        cross_material_suggestions.append({
                            "kp_id": kp.id,
                            "kp_title": kp.title,
                            "material_id": mat.id,
                            "material_title": mat.title,
                            "node_title": node.title,
                        })
                
                # 追加知识点维度薄弱信息到摘要
                if weak_knowledge_points:
                    kp_lines = []
                    for wkp in weak_knowledge_points:
                        # 收集涉及教材
                        related_materials = [
                            s["material_title"] for s in cross_material_suggestions
                            if s["kp_id"] == wkp["id"]
                        ]
                        if related_materials:
                            kp_lines.append(
                                f"- 知识点【{wkp['title']}】薄弱（涉及教材：{'、'.join(related_materials[:3])}，"
                                f"错题{wkp['mistake_count']}次）"
                            )
                        else:
                            kp_lines.append(f"- 知识点【{wkp['title']}】薄弱（错题{wkp['mistake_count']}次）")
                    mistakes_summary += "\n" + "\n".join(kp_lines)
        except Exception as e:
            # Knowledge point tables may not exist yet (before migration)
            import logging
            logging.getLogger(__name__).debug(f"KP analysis skipped: {e}")
        
        return {
            "avg_health_score": avg_score,
            "weak_nodes": weak_node_ids,
            "historical_mistakes_summary": mistakes_summary,
            "weakest_node_id": weakest.node_id,
            "weak_knowledge_points": weak_knowledge_points,
            "cross_material_suggestions": cross_material_suggestions,
        }
