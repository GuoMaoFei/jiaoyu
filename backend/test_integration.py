import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(__file__))
from app.database import get_db, Base, engine
from app.models.material import Material, KnowledgeNode
from app.services.tree_builder import TreeBuilderService
from sqlalchemy import select

async def cleanup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def test_full_pipeline():
    print("Testing full pipeline (PageIndex + tree_builder)...")
    await cleanup_db()
    
    # Need a material ID to attach it to
    from app.config import get_settings
    import uuid
    from datetime import datetime
    
    material_id = str(uuid.uuid4())
    
    async for db_session in get_db():
        # Create dummy material
        new_mat = Material(
            id=material_id, 
            title="Test Textbook", 
            grade="Test", 
            subject="Test", 
            version="1.0"
        )
        db_session.add(new_mat)
        await db_session.commit()
        
        pdf_path = r"d:\project\python\jiaoyu_agent\backend\test_small.pdf"
        if not os.path.exists(pdf_path):
            from test_parse_pipeline import create_small_pdf
            create_small_pdf()
        
        try:
            service = TreeBuilderService(db_session)
            print(f"Running ingest_material on {pdf_path}...")
            result = await service.ingest_material(material_id, pdf_path)
            print("ingest_material result:", result)
            
            # Check DB
            print("\nDatabase Nodes:")
            nodes = await db_session.execute(select(KnowledgeNode).where(KnowledgeNode.material_id == material_id))
            nodes = nodes.scalars().all()
            print(f"Total nodes saved: {len(nodes)}")
            for n in nodes:
                print(f"  [L{n.level}] #{n.seq_num} {n.title} (pi_ref={n.pageindex_ref})")
                
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
