import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(__file__))
from app.database import get_db
from sqlalchemy import text

async def clear_materials_data():
    async for db in get_db():
        print("Clearing tables...")
        tables_to_clear = [
            'chat_messages',
            'chat_assessments',
            'student_mistakes',
            'student_node_states',
            'test_papers',
            'questions',
            'book_activations',
            'knowledge_nodes',
            'materials',
            'media_assets'
        ]
        
        for table in tables_to_clear:
            try:
                await db.execute(text(f"DELETE FROM {table}"))
                print(f"Cleared {table}")
            except Exception as e:
                print(f"Error clearing {table}: {e}")
                
        await db.commit()
        print("All specified tables have been cleared. Ready for re-upload!")

if __name__ == "__main__":
    asyncio.run(clear_materials_data())
