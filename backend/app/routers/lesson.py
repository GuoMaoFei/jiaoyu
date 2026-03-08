"""
Lesson Router - Handles guided learning session lifecycle.
"""
import logging

from fastapi import APIRouter, Depends
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
async def get_study_plans(student_id: str, db: AsyncSession = Depends(get_db)):
    """Get the student's study plan items."""
    stmt = (
        select(PlanItem, KnowledgeNode.title)
        .join(KnowledgeNode, PlanItem.node_id == KnowledgeNode.id)
        .where(PlanItem.student_id == student_id)
        .order_by(PlanItem.scheduled_date.asc())
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    items = []
    for plan, title in rows:
        ftype = "LEARN_NEW"
        if plan.task_type.value == "REVIEW":
            ftype = "REVIEW_VARIANT"
            
        items.append(PlanItemResponse(
            id=plan.id,
            type=ftype,
            title=f"{'学习' if ftype == 'LEARN_NEW' else '复习'}：{title}",
            completed=plan.status.value == "COMPLETED",
            duration_min=15 if ftype == "LEARN_NEW" else 10,
            date=plan.scheduled_date.isoformat()
        ))
    return PlanListResponse(student_id=student_id, items=items)


@router.post("/plans/generate")
async def generate_study_plan(request: PlanGenerateRequest):
    """Trigger Planner Agent to generate a study plan."""
    from app.agent.graph import treeedu_graph
    from langchain_core.messages import HumanMessage
    import uuid
    
    session_id = str(uuid.uuid4())
    prompt = f"请帮我生成接下来的学习计划，从 {request.start_date or '今天'} 开始，每周 {request.sessions_per_week or 3} 次。"
    
    agent_input = {
        "session_id": session_id,
        "student_id": request.student_id,
        "material_id": request.material_id,
        "current_intent": "planner",
        "messages": [HumanMessage(content=prompt)]
    }
    config = {"configurable": {"thread_id": session_id}}
    
    final_content = ""
    try:
        async for event in treeedu_graph.astream(agent_input, config=config):
            for node_name, values in event.items():
                if "messages" in values and node_name == "planner":
                    last_msg = values["messages"][-1]
                    if hasattr(last_msg, 'content') and last_msg.content:
                        final_content = last_msg.content
    except Exception as e:
        logger.exception(f"Plan generation error: {e}")
        
    return {"status": "ok", "message": final_content or "Plan generated successfully"}
