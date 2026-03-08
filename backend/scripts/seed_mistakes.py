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
from app.models.testing import StudentMistake, MistakeStatus

sys_now = lambda: datetime.now(timezone.utc).date()

async def seed_mistakes():
    async with AsyncSessionLocal() as session:
        # Get demo student
        result = await session.execute(select(Student).where(Student.nickname == "stu_demo"))
        student = result.scalars().first()
        if not student:
            print("Demo student not found.")
            return

        # Find some nodes for mistakes
        result = await session.execute(select(KnowledgeNode).where(KnowledgeNode.title.in_(["1 天地人", "2 金木水火土", "1 a o e", "2 i u v"])))
        nodes = result.scalars().all()

        if not nodes:
            print("No suitable nodes found.")
            return

        states = []
        for i, node in enumerate(nodes):
            if "天地人" in node.title:
                states.append(StudentMistake(
                    student_id=student.id,
                    node_id=node.id,
                    error_reason="天字的笔画顺序写反了，先写了撇再写横",
                    consecutive_correct_count=0,
                    status=MistakeStatus.ACTIVE,
                    next_review_date=sys_now() + timedelta(days=0) # Due today
                ))
            elif "金木水火土" in node.title:
                states.append(StudentMistake(
                    student_id=student.id,
                    node_id=node.id,
                    error_reason="拼音掌握不熟，经常把土（tu）拼成（te）",
                    consecutive_correct_count=1,
                    status=MistakeStatus.REVIEWING,
                    next_review_date=sys_now() + timedelta(days=1)
                ))
            elif "a o e" in node.title:
                states.append(StudentMistake(
                    student_id=student.id,
                    node_id=node.id,
                    error_reason="a 和 o 的发音口型混淆",
                    consecutive_correct_count=3,
                    status=MistakeStatus.MASTERED,
                    next_review_date=None
                ))
                
        if states:
            session.add_all(states)
            await session.commit()
            print(f"Successfully seeded {len(states)} mistake records for student {student.nickname}.")
        else:
            print("No matching nodes found to seed mistakes.")

if __name__ == "__main__":
    asyncio.run(seed_mistakes())
