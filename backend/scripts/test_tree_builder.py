import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Setup paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db, Base, engine
from app.services.tree_builder import TreeBuilderService
from app.models.material import Material, MaterialType, KnowledgeNode
from sqlalchemy import select

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def test_tree_builder():
    load_dotenv()
    
    if not os.getenv("ALIYUN_API_KEY"):
        logger.warning("Please set ALIYUN_API_KEY in your .env file for local PageIndex extraction")

    await setup_db()
    
    async for db in get_db():
        try:
            # 1. Create a dummy material
            dummy_material = Material(
                title="Test Material - Vectorless RAG Cookbook",
                grade="General",
                subject="Computer Science",
                version="1.0",
                publisher="VectifyAI",
                material_type=MaterialType.EXTERNAL
            )
            db.add(dummy_material)
            await db.commit()
            logger.info(f"Created dummy material with ID: {dummy_material.id}")
            
            # 2. Initialize service
            builder = TreeBuilderService(db_session=db)
            
            # 3. Test URL (the same one used in the pageindex cookbook)
            pdf_url = "https://arxiv.org/pdf/2501.12948.pdf"
            
            logger.info(f"Starting ingestion of {pdf_url}...")
            result = await builder.ingest_material(material_id=dummy_material.id, pdf_url_or_path=pdf_url)
            
            logger.info("Ingestion complete!")
            logger.info(result)
            
            # 4. Verify nodes in DB
            result = await db.execute(select(KnowledgeNode).where(KnowledgeNode.material_id == dummy_material.id))
            nodes = result.scalars().all()
            
            logger.info(f"Successfully saved {len(nodes)} knowledge nodes to the database.")
            for node in nodes[:5]: # print first 5
                logger.info(f"- Level {node.level}: {node.title} (pi_ref: {node.pageindex_ref})")
            
        except ImportError as e:
            logger.error(f"Import Error: {e}")
        except Exception as e:
            logger.exception(f"An error occurred: {e}")
            await db.rollback()
        finally:
            # We don't want to pollute DB for real, but this is a test script
            # In a real test we'd rollback
            break

if __name__ == "__main__":
    asyncio.run(test_tree_builder())
