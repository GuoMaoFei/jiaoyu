import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.models.material import Material, MaterialType, KnowledgeNode, KnowledgeContent
from app.services.tree_builder import TreeBuilderService

async def main():
    db_url = "sqlite+aiosqlite:///treeedu.db"
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with async_session() as db:
        # Create material
        material = Material(
            title="测试上传PDF教材",
            grade="一年级",
            subject="数学",
            version="2024测试版",
            publisher="系统自动",
            material_type=MaterialType.OFFICIAL,
        )
        db.add(material)
        await db.commit()
        await db.refresh(material)
        print(f"1. Created Material ID: {material.id}")
        
        # Run TreeBuilderService
        builder = TreeBuilderService(db_session=db)
        pdf_path = "mock_textbook_math_grade1.pdf"
        print(f"2. Starting PDF PageIndex Ingestion for {pdf_path}...")
        try:
            res = await builder.ingest_material(material.id, pdf_path)
            print(f"Ingestion Finished. Status: {res.get('status')}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("Ingestion failed:", e)
            return

        print("\n--- 3. Verifying Database Records ---")
        # Assert Data
        stmt_nodes = select(KnowledgeNode).where(KnowledgeNode.material_id == material.id)
        res_nodes = await db.execute(stmt_nodes)
        nodes = res_nodes.scalars().all()
        print(f"Total KnowledgeNodes created: {len(nodes)}")
        
        json_fields_populated = 0
        for n in nodes:
            has_json = bool(n.pi_nodes_json)
            if has_json: json_fields_populated += 1
            print(f"  - Node [{n.level}]: {n.title} (pi_nodes_json exists: {has_json})")
            
        stmt_content = select(KnowledgeContent).where(
            KnowledgeContent.knowledge_node_id.in_([n.id for n in nodes])
        )
        res_content = await db.execute(stmt_content)
        contents = res_content.scalars().all()
        print(f"Total KnowledgeContents created: {len(contents)}")
        
        for c in contents:
            parent = next((n.title for n in nodes if n.id == c.knowledge_node_id), "Unknown")
            preview = c.content_md.replace('\n', ' ')[:50] + "..." if len(c.content_md) > 50 else c.content_md.replace('\n', ' ')
            print(f"  - Content attached to: [{parent}] -> Length: {len(c.content_md)} | Preview: {preview}")
            
        print("\n--- 4. Verification Summary ---")
        if len(contents) > 0 and json_fields_populated > 0:
            print("✅ SUCCESS: Schema decoupling works! `pi_nodes_json` has structure, `KnowledgeContent` holds text data.")
        else:
            print("❌ FAILED: Either contents weren't extracted or json field was empty!")

if __name__ == "__main__":
    asyncio.run(main())
