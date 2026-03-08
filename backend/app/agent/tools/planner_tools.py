"""
Planner Tools - Database write tools for the Planner Agent to generate study plans.
"""
from typing import List
from datetime import date, timedelta
from langchain_core.tools import tool
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.lesson import PlanItem, PlanStatus, TaskType
from app.models.material import KnowledgeNode


@tool
async def create_study_plan(
    student_id: str,
    node_ids: List[str],
    start_date: str,
    sessions_per_week: int = 3
) -> str:
    """
    Create a study plan by scheduling knowledge nodes across dates.
    
    Args:
        student_id: The student's unique ID.
        node_ids: Ordered list of knowledge node IDs to schedule.
        start_date: Start date in YYYY-MM-DD format.
        sessions_per_week: Number of study sessions per week (default 3).
    
    Returns:
        A confirmation string with the number of plan items created.
    """
    async with AsyncSessionLocal() as db:
        try:
            start = date.fromisoformat(start_date)
            
            # Distribute nodes across available sessions
            # Create sessions on Mon/Wed/Fri or spread evenly
            plan_items = []
            current_date = start
            session_count = 0
            
            for node_id in node_ids:
                # Skip weekends for scheduling
                while current_date.weekday() >= 5:  # Saturday=5, Sunday=6
                    current_date += timedelta(days=1)
                
                plan_item = PlanItem(
                    student_id=student_id,
                    node_id=node_id,
                    scheduled_date=current_date,
                    task_type=TaskType.NEW_KNOWLEDGE,
                    status=PlanStatus.PENDING,
                )
                db.add(plan_item)
                plan_items.append(plan_item)
                
                session_count += 1
                if session_count >= sessions_per_week:
                    # Move to next week
                    current_date += timedelta(days=7 - current_date.weekday())
                    session_count = 0
                else:
                    # Move to next weekday (skip 1-2 days)
                    days_gap = max(1, 7 // sessions_per_week)
                    current_date += timedelta(days=days_gap)
            
            await db.commit()
            
            date_range = f"{start.isoformat()} ~ {current_date.isoformat()}"
            return (
                f"学习计划创建成功！共安排 {len(plan_items)} 个学习节点，"
                f"时间跨度：{date_range}，每周 {sessions_per_week} 课时。"
            )
        except Exception as e:
            await db.rollback()
            return f"创建学习计划失败：{str(e)}"


@tool
async def get_material_node_list(material_id: str) -> str:
    """
    Get the full list of knowledge nodes for a material, ordered by level and sequence.
    Use this to understand the curriculum structure before creating a study plan.
    
    Args:
        material_id: The material/textbook ID.
    
    Returns:
        A formatted list of all nodes with their IDs, levels, and titles.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KnowledgeNode)
            .where(KnowledgeNode.material_id == material_id)
            .order_by(KnowledgeNode.level, KnowledgeNode.seq_num)
        )
        nodes = result.scalars().all()
        
        if not nodes:
            return f"教材 {material_id} 暂无知识树节点。请先通过 PageIndex 构建知识树。"
        
        output = [f"教材知识树结构（共 {len(nodes)} 个节点）："]
        for n in nodes:
            indent = "  " * (n.level - 1)
            output.append(f"{indent}[Level {n.level}] {n.title} (id: {n.id})")
        
        return "\n".join(output)
