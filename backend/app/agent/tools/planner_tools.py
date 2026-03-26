"""
Planner Tools - Database write tools for Planner Agent to generate study plans.
"""

from typing import List, Optional
from datetime import date, timedelta
from uuid import UUID
from langchain_core.tools import tool
from sqlalchemy import select, func
from sqlalchemy.orm import aliased
from app.database import AsyncSessionLocal
from app.models.lesson import PlanItem, PlanStatus, TaskType, LessonProgress
from app.models.material import KnowledgeNode, KnowledgeContent


def is_valid_uuid(val: str) -> bool:
    """Check if string is a valid UUID format."""
    try:
        UUID(val)
        return True
    except (ValueError, AttributeError):
        return False


@tool
async def get_material_node_list(
    material_id: str, student_id: Optional[str] = None
) -> str:
    """
    Get the list of lesson nodes (Level 2) for a material in chapter order.
    Only returns nodes that have KnowledgeContent and the student has NOT completed.
    The nodes are sorted by chapter order: parent chapter's seq_num, then node's seq_num.

    Args:
        material_id: The material/textbook ID.
        student_id: (Optional) The student's ID to check completion status.

    Returns:
        A formatted list of UNCOMPLETED lesson nodes sorted by chapter order.
    """
    async with AsyncSessionLocal() as db:
        nodes_with_content = select(KnowledgeContent.knowledge_node_id).where(
            KnowledgeContent.knowledge_node_id.isnot(None)
        )

        parent = aliased(KnowledgeNode)

        base_where = [
            KnowledgeNode.material_id == material_id,
            KnowledgeNode.id.in_(nodes_with_content),
            KnowledgeNode.level == 2,
        ]

        if student_id:
            completed_subquery = select(LessonProgress.node_id).where(
                LessonProgress.student_id == student_id,
                LessonProgress.is_completed == True,
            )
            base_where.append(KnowledgeNode.id.not_in(completed_subquery))

        query = (
            select(
                KnowledgeNode.id,
                KnowledgeNode.title,
                KnowledgeNode.level,
                KnowledgeNode.seq_num,
                parent.seq_num.label("parent_seq_num"),
            )
            .select_from(KnowledgeNode)
            .outerjoin(parent, KnowledgeNode.parent_id == parent.id)
            .where(*base_where)
            .order_by(
                func.coalesce(parent.seq_num, 0).asc(),
                KnowledgeNode.seq_num.asc(),
            )
        )

        result = await db.execute(query)
        nodes = result.all()

        if not nodes:
            return f"教材 {material_id} 暂无可学习的课文节点。"

        output = [f"可学习课文列表（共 {len(nodes)} 篇，按章节顺序）："]
        for n in nodes:
            output.append(f"- {n.title} (id: {n.id})")

        output.append(
            "\n节点已按章节顺序排列，请直接使用上述节点 ID 调用 create_study_plan。"
        )
        return "\n".join(output)


@tool
async def create_study_plan(
    student_id: str,
    material_id: str,
    node_ids: List[str],
    start_date: str,
    sessions_per_week: int = 3,
) -> str:
    """
    Create a study plan by scheduling knowledge nodes across dates.

    Args:
        student_id: The student's unique ID.
        material_id: The material/textbook ID for this plan.
        node_ids: Ordered list of knowledge node IDs to schedule. MUST be valid UUIDs.
        start_date: Start date in YYYY-MM-DD format.
        sessions_per_week: Number of study sessions per week (default 3).

    Returns:
        A confirmation string with number of plan items created.
    """
    invalid_ids = [nid for nid in node_ids if not is_valid_uuid(nid)]
    if invalid_ids:
        return f"错误：无效的节点 ID 格式 {invalid_ids}。请使用 UUID 格式（如 'e1cd2afe-c53f-4f32-bc26-8c69e1e7ddf6'），而不是 'node_001' 这样的旧格式。"

    async with AsyncSessionLocal() as db:
        try:
            start = date.fromisoformat(start_date)

            plan_items = []
            current_date = start
            session_count = 0

            for node_id in node_ids:
                while current_date.weekday() >= 5:
                    current_date += timedelta(days=1)

                plan_item = PlanItem(
                    student_id=student_id,
                    node_id=node_id,
                    material_id=material_id,
                    scheduled_date=current_date,
                    task_type=TaskType.NEW_KNOWLEDGE,
                    status=PlanStatus.PENDING,
                )
                db.add(plan_item)
                plan_items.append(plan_item)

                session_count += 1
                if session_count >= sessions_per_week:
                    current_date += timedelta(days=7 - current_date.weekday())
                    session_count = 0
                else:
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
