import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Ensure we can import from the app module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from app.models.user import Student, StudentNodeState
from app.models.material import KnowledgeNode
from app.models.testing import StudentMistake, MistakeStatus
from app.models.chat import ChatAssessment

sys_today = lambda: datetime.now(timezone.utc).date()

async def seed_report_data():
    async with AsyncSessionLocal() as session:
        # Get demo student
        result = await session.execute(select(Student).where(Student.nickname == "stu_demo"))
        student = result.scalars().first()
        if not student:
            print("Demo student not found.")
            return

        # Find nodes for 天地人 / 金木水火土 / a o e
        result = await session.execute(select(KnowledgeNode).where(KnowledgeNode.title.in_(
            ["1 天地人", "2 金木水火土", "1 a o e"]
        )))
        nodes = result.scalars().all()
        node_map = {n.title: n for n in nodes}

        # Insert Node States
        states = []
        if "1 天地人" in node_map:
            states.append(StudentNodeState(
                student_id=student.id, node_id=node_map["1 天地人"].id, health_score=95, is_unlocked=True
            ))
        if "2 金木水火土" in node_map:
            states.append(StudentNodeState(
                student_id=student.id, node_id=node_map["2 金木水火土"].id, health_score=65, is_unlocked=True
            ))
        if "1 a o e" in node_map:
            states.append(StudentNodeState(
                student_id=student.id, node_id=node_map["1 a o e"].id, health_score=40, is_unlocked=True
            ))
            
        # Clear old states to avoid conflicts
        await session.execute(StudentNodeState.__table__.delete().where(StudentNodeState.student_id == student.id))
        session.add_all(states)
        
        # Insert Mistakes
        mistakes = []
        if "2 金木水火土" in node_map:
            mistakes.append(StudentMistake(
                student_id=student.id, node_id=node_map["2 金木水火土"].id,
                error_reason="书写笔画顺序颠倒，对‘水’字的弯钩不熟悉",
                status=MistakeStatus.REVIEWING, consecutive_correct_count=1
            ))
        if "1 a o e" in node_map:
            mistakes.append(StudentMistake(
                student_id=student.id, node_id=node_map["1 a o e"].id,
                error_reason="发音口型不对，把 e 读成了 o",
                status=MistakeStatus.ACTIVE, consecutive_correct_count=0
            ))
            mistakes.append(StudentMistake(
                student_id=student.id, node_id=node_map["1 a o e"].id,
                error_reason="拼音字形记混，把 a 写成了 o",
                status=MistakeStatus.ACTIVE, consecutive_correct_count=0
            ))
            
        await session.execute(StudentMistake.__table__.delete().where(StudentMistake.student_id == student.id))
        session.add_all(mistakes)
        
        await session.commit()
        print(f"Successfully seeded report data for student {student.nickname}.")

if __name__ == "__main__":
    asyncio.run(seed_report_data())
