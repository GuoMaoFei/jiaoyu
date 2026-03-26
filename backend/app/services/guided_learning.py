"""
Guided Learning Service - Five-step state machine for structured learning sessions.

The five steps are:
1. IMPORT   — 基础预热：给出课件节点的核心概念摘要
2. EXPLAIN  — 深入讲解：引导式对话教学
3. EXAMPLE  — 典型例题：展示标准解题过程
4. PRACTICE — 上手实操：学生独立做练习
5. SUMMARY  — 总结回顾：知识要点复盘
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.lesson import LessonProgress, LessonStep, PlanItem, PlanStatus
from app.models.material import KnowledgeNode
from app.models.user import StudentNodeState

logger = logging.getLogger(__name__)

# Define step transitions
STEP_ORDER = [
    LessonStep.IMPORT,
    LessonStep.EXPLAIN,
    LessonStep.EXAMPLE,
    LessonStep.PRACTICE,
    LessonStep.SUMMARY,
    LessonStep.COMPLETED,
]

STEP_PROMPTS = {
    LessonStep.IMPORT: (
        "你现在进入了【预热导入】阶段。请先快速浏览本节内容的核心概念。\n"
        "节点标题：{node_title}\n内容摘要：{content_preview}\n\n"
        "准备好了吗？回复「继续」进入讲解阶段。"
    ),
    LessonStep.EXPLAIN: (
        "你现在进入了【深入讲解】阶段。接下来 Tutor 会通过引导式对话帮你理解本节的核心知识点。\n"
        "请随时向 Tutor 提问！"
    ),
    LessonStep.EXAMPLE: (
        "你现在进入了【典型例题】阶段。下面是一道和本节知识点相关的例题，"
        "请仔细阅读解题过程并尝试理解每一步。\n"
        "看完后回复「继续」开始实操练习。"
    ),
    LessonStep.PRACTICE: (
        "你现在进入了【上手实操】阶段。请独立完成以下练习题。\n"
        "完成后 Assessor 会自动评分并记录到你的知识树档案中。"
    ),
    LessonStep.SUMMARY: (
        "你现在进入了【总结回顾】阶段。让我们一起复盘本节卡的知识要点：\n"
        "回复「完成」结束本节学习。"
    ),
}


async def get_or_create_lesson(
    student_id: str,
    node_id: str,
) -> Dict[str, Any]:
    """Get or create a lesson progress record for a student-node pair."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(LessonProgress).where(
                LessonProgress.student_id == student_id,
                LessonProgress.node_id == node_id,
            )
        )
        lesson = result.scalars().first()

        if not lesson:
            lesson = LessonProgress(
                student_id=student_id,
                node_id=node_id,
                current_step=LessonStep.IMPORT,
            )
            db.add(lesson)
            await db.commit()
            await db.refresh(lesson)

        # Get node info for prompts
        node_result = await db.execute(
            select(KnowledgeNode).where(KnowledgeNode.id == node_id)
        )
        node = node_result.scalars().first()

        node_title = node.title if node else "Unknown"
        _pi_summary = ""
        if (
            node
            and node.pi_nodes_json
            and isinstance(node.pi_nodes_json, list)
            and len(node.pi_nodes_json) > 0
        ):
            _pi_summary = node.pi_nodes_json[0].get("summary", "")
        content_preview = (_pi_summary[:300] + "...") if _pi_summary else "暂无内容"

        return {
            "lesson_id": lesson.id,
            "student_id": lesson.student_id,
            "node_id": lesson.node_id,
            "material_id": node.material_id if node else None,
            "current_step": lesson.current_step.value,
            "is_completed": lesson.is_completed,
            "node_title": node_title,
            "content_preview": content_preview,
            "step_prompt": STEP_PROMPTS.get(lesson.current_step, "").format(
                node_title=node_title, content_preview=content_preview
            ),
        }


async def _fetch_or_generate_example(node_id: str) -> str:
    """查询已有例题，如果不存在则调用 Variant Agent 生成一道（简化版：当前仅查询）"""
    from app.models.material import Question

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Question).where(Question.node_id == node_id).limit(1)
        )
        q = result.scalars().first()
        if q:
            return f"**【例题】**\n{q.content_md}"
        else:
            return "**【例题】**\n（题库中暂无此节点的例题，请 Tutor 给出一道简单的示例题）"


async def advance_lesson_step(
    student_id: str,
    node_id: str,
) -> Dict[str, Any]:
    """Advance the lesson to the next step in the state machine."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(LessonProgress).where(
                LessonProgress.student_id == student_id,
                LessonProgress.node_id == node_id,
            )
        )
        lesson = result.scalars().first()

        if not lesson:
            return {"error": "No lesson found. Please start a lesson first."}

        # Get node info to have material_id
        node_result = await db.execute(
            select(KnowledgeNode).where(KnowledgeNode.id == node_id)
        )
        node = node_result.scalars().first()

        if lesson.is_completed:
            return {
                "lesson_id": lesson.id,
                "current_step": LessonStep.COMPLETED.value,
                "is_completed": True,
                "material_id": node.material_id if node else None,
                "message": "本节学习已完成！可以开始下一个知识节点了。",
            }

        # Find next step
        current_index = STEP_ORDER.index(lesson.current_step)
        if current_index < len(STEP_ORDER) - 1:
            next_step = STEP_ORDER[current_index + 1]
            lesson.current_step = next_step
            lesson.last_interacted_at = datetime.now(timezone.utc)

            if next_step == LessonStep.COMPLETED:
                lesson.is_completed = True
                # Unlock the node in student's state
                ns_result = await db.execute(
                    select(StudentNodeState).where(
                        StudentNodeState.student_id == student_id,
                        StudentNodeState.node_id == node_id,
                    )
                )
                node_state = ns_result.scalars().first()
                if node_state:
                    node_state.health_score = min(100, node_state.health_score + 10)
                else:
                    node_state = StudentNodeState(
                        student_id=student_id,
                        node_id=node_id,
                        is_unlocked=True,
                        health_score=60,
                    )
                    db.add(node_state)

                # Update corresponding PlanItem status to COMPLETED
                plan_result = await db.execute(
                    select(PlanItem).where(
                        PlanItem.student_id == student_id,
                        PlanItem.node_id == node_id,
                    )
                )
                plan_item = plan_result.scalars().first()
                if plan_item:
                    plan_item.status = PlanStatus.COMPLETED
                    plan_item.completed_at = datetime.now(timezone.utc)

            await db.commit()

        node_title = node.title if node else "Unknown"
        _pi_summary2 = ""
        if (
            node
            and node.pi_nodes_json
            and isinstance(node.pi_nodes_json, list)
            and len(node.pi_nodes_json) > 0
        ):
            _pi_summary2 = node.pi_nodes_json[0].get("summary", "")
        content_preview = (_pi_summary2[:300] + "...") if _pi_summary2 else "暂无内容"

        step_prompt = ""
        example_content = ""

        if lesson.is_completed:
            step_prompt = "🎉 恭喜你完成了本节的全部学习！"
        else:
            # 基础模板
            base_prompt = STEP_PROMPTS.get(lesson.current_step, "")
            step_prompt = base_prompt.format(
                node_title=node_title, content_preview=content_preview
            )

            # 动态增强
            if lesson.current_step == LessonStep.EXAMPLE:
                example_content = await _fetch_or_generate_example(node_id)
                step_prompt = (
                    f"{step_prompt}\n\n系统已提取例题，Tutor 将开始引导你去解答它。"
                )

        return {
            "lesson_id": lesson.id,
            "node_id": node_id,
            "node_title": node_title,
            "current_step": lesson.current_step.value,
            "is_completed": lesson.is_completed,
            "material_id": node.material_id if node else None,
            "step_prompt": step_prompt,
            "example_content": example_content,  # Pass it out so the router can catch it
        }
