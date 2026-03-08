import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.services.memory_overlay import get_student_memory_overlay

async def main():
    student_id = "1b928e2c-15fd-47eb-b260-4de16062752f" # the stu_demo ID from the previous run
    try:
        overlay = await get_student_memory_overlay(student_id)
        print("Success:", overlay)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
