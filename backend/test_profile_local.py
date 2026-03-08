import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.routers.student import get_student_profile

async def main():
    student_id = "1b928e2c-15fd-47eb-b260-4de16062752f" # the stu_demo ID
    async with AsyncSessionLocal() as db:
        try:
            resp = await get_student_profile(student_id, db)
            print("Success:", resp)
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
