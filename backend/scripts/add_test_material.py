import asyncio
import httpx
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://127.0.0.1:8000/api"
STUDENT_ID = "stu_demo" # Let's fetch the actual ID by logging in first.

os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""
os.environ["NO_PROXY"] = "*"

async def main():
    async with httpx.AsyncClient() as client:
        # 1. Login to get student_id
        print("Logging in...")
        try:
            resp = await client.post(f"{BASE_URL}/students/login", json={"username": "stu_demo", "password": "123"})
            if resp.status_code != 200:
                print(f"Login failed: status={resp.status_code} text={resp.text}")
                return
            
            student_id = resp.json()["student_id"]
            print(f"Logged in as {student_id}")
        except Exception as e:
            print("Login exception:", e)
            return

        # 2. Create material
        print("Creating material...")
        mat_req = {
            "title": "语文一年级上册（人教版）",
            "grade": "一年级",
            "subject": "语文",
            "version": "2022年版"
        }
        resp = await client.post(f"{BASE_URL}/materials/", json=mat_req)
        if resp.status_code != 200:
            print("Failed to create material:", resp.text)
            return
        
        material_id = resp.json()["id"]
        print(f"Created material {material_id}")

        print("Building mock knowledge tree (Bypassing PageIndex due to API limit)...")
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        
        # Connect directly to DB since we are in backend dir
        engine = create_async_engine("sqlite+aiosqlite:///treeedu.db")
        async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        
        async with async_session() as db:
            from app.models.material import KnowledgeNode
            import uuid
            
            # Chapter 1
            ch1_id = str(uuid.uuid4())
            db.add(KnowledgeNode(id=ch1_id, material_id=material_id, title="第一单元：识字", level=1, seq_num=1, content_md="识字单元介绍..."))
            db.add(KnowledgeNode(id=str(uuid.uuid4()), material_id=material_id, parent_id=ch1_id, title="1 天地人", level=2, seq_num=1, content_md="天地人，你我他..."))
            db.add(KnowledgeNode(id=str(uuid.uuid4()), material_id=material_id, parent_id=ch1_id, title="2 金木水火土", level=2, seq_num=2, content_md="一二三四五，金木水火土..."))
            
            # Chapter 2
            ch2_id = str(uuid.uuid4())
            db.add(KnowledgeNode(id=ch2_id, material_id=material_id, title="第二单元：汉语拼音", level=1, seq_num=2, content_md="拼音基础..."))
            db.add(KnowledgeNode(id=str(uuid.uuid4()), material_id=material_id, parent_id=ch2_id, title="1 a o e", level=2, seq_num=1, content_md="张大嘴巴 a a a..."))
            db.add(KnowledgeNode(id=str(uuid.uuid4()), material_id=material_id, parent_id=ch2_id, title="2 i u v", level=2, seq_num=2, content_md="牙齿对齐 i i i..."))
            
            await db.commit()
            print("Mock tree built successfully.")

        # 4. Activate book for student
        print("Activating book for student...")
        act_req = {
            "student_id": student_id,
            "material_id": material_id
        }
        resp = await client.post(f"{BASE_URL}/students/activate-book", json=act_req)
        if resp.status_code not in (200, 409): # 409 means already activated
            print("Failed to activate book:", resp.text)
            return
        print("Book activated successfully!")

if __name__ == "__main__":
    asyncio.run(main())
