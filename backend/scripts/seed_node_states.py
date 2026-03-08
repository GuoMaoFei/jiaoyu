import asyncio
import sys
import os

# Ensure we can import from the app module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import Student, StudentNodeState
from app.models.material import Material, KnowledgeNode

async def seed_student_states():
    async with AsyncSessionLocal() as session:
        # Get demo student
        result = await session.execute(select(Student).where(Student.nickname == "stu_demo"))
        student = result.scalars().first()
        if not student:
            print("Demo student not found.")
            return

        # Get demo student
        result = await session.execute(select(Student).where(Student.nickname == "stu_demo"))
        student = result.scalars().first()
        if not student:
            print("Demo student not found.")
            return

        # Get all nodes matching the test titles
        result = await session.execute(select(KnowledgeNode))
        nodes = result.scalars().all()

        if not nodes:
            print("No nodes found in database.")
            return

        # Seed states
        # Root node: unlocked, health 75
        # "1 天地人": unlocked, health 90
        # "2 金木水火土": unlocked, health 50
        
        states = []
        for node in nodes:
            print(f"Found node: '{node.title}' (ID: {node.id})")
            if "识字" in node.title:
                states.append(StudentNodeState(student_id=student.id, node_id=node.id, is_unlocked=True, health_score=75))
            elif "天地人" in node.title:
                states.append(StudentNodeState(student_id=student.id, node_id=node.id, is_unlocked=True, health_score=90))
            elif "金木水火土" in node.title:
                states.append(StudentNodeState(student_id=student.id, node_id=node.id, is_unlocked=True, health_score=50))
            # Fallback to unlock all other nodes with 0 health for testing
            else:
                states.append(StudentNodeState(student_id=student.id, node_id=node.id, is_unlocked=True, health_score=10))
                
        if states:
            session.add_all(states)
            await session.commit()
            print(f"Successfully seeded {len(states)} node states for student {student.nickname}.")
        else:
            print("No matching nodes found to seed.")

if __name__ == "__main__":
    asyncio.run(seed_student_states())
