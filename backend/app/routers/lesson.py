"""
Lesson Router - Handles guided learning session lifecycle.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.services.guided_learning import get_or_create_lesson, advance_lesson_step
from app.models.lesson import PlanItem
from app.models.material import KnowledgeNode
from app.schemas.lesson import (
    LessonStartRequest,
    LessonAdvanceRequest,
    LessonStatusResponse,
    PlanListResponse,
    PlanItemResponse,
    PlanGenerateRequest,
)
from app.models.material import Material

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lessons", tags=["Lessons"])


@router.post("/start", response_model=LessonStatusResponse)
async def start_lesson(request: LessonStartRequest):
    """
    Start or resume a guided learning session for a specific knowledge node.
    Returns the current step and its prompt.
    """
    result = await get_or_create_lesson(request.student_id, request.node_id)
    return LessonStatusResponse(**result)


@router.post("/advance", response_model=LessonStatusResponse)
async def advance_step(request: LessonAdvanceRequest):
    """
    Advance the lesson to the next step.
    Steps: IMPORT → EXPLAIN → EXAMPLE → PRACTICE → SUMMARY → COMPLETED
    """
    result = await advance_lesson_step(request.student_id, request.node_id)
    return LessonStatusResponse(**result)


@router.get("/plans/{student_id}", response_model=PlanListResponse)
async def get_study_plans(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    material_id: Optional[str] = Query(None, description="Filter by material ID"),
):
    """Get the student's study plan items, optionally filtered by material."""
    stmt = (
        select(PlanItem, KnowledgeNode.title, Material.subject)
        .outerjoin(KnowledgeNode, PlanItem.node_id == KnowledgeNode.id)
        .outerjoin(Material, PlanItem.material_id == Material.id)
        .where(PlanItem.student_id == student_id)
    )

    if material_id:
        stmt = stmt.where(PlanItem.material_id == material_id)

    stmt = stmt.order_by(PlanItem.scheduled_date.asc())

    result = await db.execute(stmt)
    rows = result.all()

    items = []
    start_date = None
    end_date = None

    for plan, title, subject in rows:
        ftype = "LEARN_NEW"
        if plan.task_type.value == "REVIEW":
            ftype = "REVIEW_VARIANT"

        node_title = title if title else f"节点 {plan.node_id}"

        if start_date is None:
            start_date = plan.scheduled_date.isoformat()
        end_date = plan.scheduled_date.isoformat()

        items.append(
            PlanItemResponse(
                id=plan.id,
                node_id=plan.node_id,
                material_id=plan.material_id,
                subject=subject,
                type=ftype,
                title=f"{'学习' if ftype == 'LEARN_NEW' else '复习'}：{node_title}",
                completed=plan.status.value == "COMPLETED",
                duration_min=15 if ftype == "LEARN_NEW" else 10,
                date=plan.scheduled_date.isoformat(),
            )
        )
    return PlanListResponse(
        student_id=student_id, items=items, start_date=start_date, end_date=end_date
    )


@router.post("/plans/generate")
async def generate_study_plan(request: PlanGenerateRequest):
    """Trigger Planner Agent to generate a study plan."""
    from app.agent.graph import treeedu_graph
    from langchain_core.messages import HumanMessage
    import uuid
    from datetime import datetime

    session_id = str(uuid.uuid4())
    start_date = request.start_date or datetime.now().strftime("%Y-%m-%d")
    sessions = request.sessions_per_week or 3
    prompt = f"""请帮我生成接下来的学习计划。

重要要求：
1. 开始日期必须是 {start_date}（格式：YYYY-MM-DD）
2. 每周学习 {sessions} 次
3. 请直接调用 create_study_plan 工具创建计划，不要自己估算日期
"""

    agent_input = {
        "session_id": session_id,
        "student_id": request.student_id,
        "material_id": request.material_id,
        "current_intent": "planner",
        "messages": [HumanMessage(content=prompt)],
    }
    config = {"configurable": {"thread_id": session_id}}

    final_content = ""
    try:
        async for event in treeedu_graph.astream(agent_input, config=config):
            for node_name, values in event.items():
                if "messages" in values and node_name == "planner":
                    last_msg = values["messages"][-1]
                    if hasattr(last_msg, "content") and last_msg.content:
                        final_content = last_msg.content
    except Exception as e:
        logger.exception(f"Plan generation error: {e}")

    return {"status": "ok", "message": final_content or "Plan generated successfully"}


@router.delete("/plans/{student_id}")
async def clear_study_plans(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    material_id: Optional[str] = Query(
        None, description="Delete plans for specific material only"
    ),
):
    """Clear study plans for a student. If material_id provided, only delete that material's plans."""
    from sqlalchemy import delete

    stmt = delete(PlanItem).where(PlanItem.student_id == student_id)
    if material_id:
        stmt = stmt.where(PlanItem.material_id == material_id)

    await db.execute(stmt)
    await db.commit()

    if material_id:
        return {"status": "ok", "message": f"教材 {material_id} 的学习计划已清除"}
    return {"status": "ok", "message": "学习计划已清除"}
