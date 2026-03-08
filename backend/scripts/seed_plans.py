import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone

# Ensure we can import from the app module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import Student
from app.models.material import KnowledgeNode
from app.models.lesson import PlanItem, TaskType, PlanStatus

sys_today = lambda: datetime.now(timezone.utc).date()

async def seed_plans():
    async with AsyncSessionLocal() as session:
        # Get demo student
        result = await session.execute(select(Student).where(Student.nickname == "stu_demo"))
        student = result.scalars().first()
        if not student:
            print("Demo student not found.")
            return

        # Find some nodes to schedule
        result = await session.execute(select(KnowledgeNode).where(KnowledgeNode.title.in_(
            ["第一单元：识字", "1 天地人", "2 金木水火土", "第二单元：汉语拼音", "1 a o e", "2 i u v"]
        )))
        nodes = result.scalars().all()

        if not nodes:
            print("No suitable nodes found.")
            return

        states = []
        today = sys_today()
        
        for i, node in enumerate(nodes):
            if "天地人" in node.title:
                # Past completed task
                states.append(PlanItem(
                    student_id=student.id,
                    node_id=node.id,
                    scheduled_date=today - timedelta(days=2),
                    task_type=TaskType.NEW_KNOWLEDGE,
                    status=PlanStatus.COMPLETED,
                    completed_at=datetime.now(timezone.utc) - timedelta(days=2)
                ))
            elif "金木水火土" in node.title:
                # Today's tasks (one new, one review from past)
                states.append(PlanItem(
                    student_id=student.id,
                    node_id=node.id,
                    scheduled_date=today,
                    task_type=TaskType.NEW_KNOWLEDGE,
                    status=PlanStatus.PENDING
                ))
                states.append(PlanItem(
                    student_id=student.id,
                    node_id=node.id,
                    scheduled_date=today,
                    task_type=TaskType.REVIEW,
                    status=PlanStatus.PENDING
                ))
            elif "a o e" in node.title:
                # Future task
                states.append(PlanItem(
                    student_id=student.id,
                    node_id=node.id,
                    scheduled_date=today + timedelta(days=1),
                    task_type=TaskType.NEW_KNOWLEDGE,
                    status=PlanStatus.PENDING
                ))
            elif "i u v" in node.title:
                # Future task
                states.append(PlanItem(
                    student_id=student.id,
                    node_id=node.id,
                    scheduled_date=today + timedelta(days=3),
                    task_type=TaskType.NEW_KNOWLEDGE,
                    status=PlanStatus.PENDING
                ))
                
        if states:
            session.add_all(states)
            await session.commit()
            print(f"Successfully seeded {len(states)} plan items for student {student.nickname}.")
        else:
            print("No matching nodes found to seed plans.")

if __name__ == "__main__":
    asyncio.run(seed_plans())
