"""Test script for 语文必修上册 PDF with LLM optimization tracking."""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func

from app.models.material import Material, MaterialType, KnowledgeNode, KnowledgeContent
from app.services.tree_builder import TreeBuilderService


PDF_PATH = r"C:\Users\茂飞\Downloads\普通高中教科书·语文必修 上册.pdf"


async def main():
    if not os.path.exists(PDF_PATH):
        print(f"ERROR: PDF not found at {PDF_PATH}")
        return

    print(f"PDF: {PDF_PATH}")
    print(f"Size: {os.path.getsize(PDF_PATH) / 1024 / 1024:.1f} MB")
    print("=" * 60)

    db_url = "sqlite+aiosqlite:///treeedu.db"
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with async_session() as db:
        # Create material
        material = Material(
            title="普通高中教科书·语文必修 上册",
            grade="高一",
            subject="语文",
            version="必修上册",
            publisher="人民教育出版社",
            material_type=MaterialType.OFFICIAL,
        )
        db.add(material)
        await db.commit()
        await db.refresh(material)
        print(f"Material ID: {material.id}")
        print("=" * 60)

        # Run TreeBuilderService with timing
        builder = TreeBuilderService(db_session=db)
        print("Starting ingest_material()...")
        print("-" * 60)

        start_time = time.time()
        try:
            res = await builder.ingest_material(material.id, PDF_PATH)
            elapsed = time.time() - start_time
            print("-" * 60)
            print(f"Ingestion Finished in {elapsed:.1f}s")
            print(f"Status: {res.get('status')}")
            print(f"Node count: {res.get('node_count')}")
        except Exception as e:
            elapsed = time.time() - start_time
            import traceback
            traceback.print_exc()
            print(f"Ingestion FAILED after {elapsed:.1f}s: {e}")
            return

        # Print LLM optimization stats
        print("\n" + "=" * 60)
        print("LLM OPTIMIZATION STATS")
        print("=" * 60)
        try:
            from pageindex.utils import get_llm_tracker
            tracker = get_llm_tracker()
            tracker.summary()
        except Exception as e:
            print(f"Could not get LLM tracker stats: {e}")

        # Verify database records
        print("\n" + "=" * 60)
        print("DATABASE VERIFICATION")
        print("=" * 60)

        stmt_nodes = select(KnowledgeNode).where(
            KnowledgeNode.material_id == material.id
        ).order_by(KnowledgeNode.level, KnowledgeNode.seq_num)
        res_nodes = await db.execute(stmt_nodes)
        nodes = res_nodes.scalars().all()
        print(f"Total KnowledgeNodes: {len(nodes)}")

        # Group by level
        by_level = {}
        for n in nodes:
            by_level.setdefault(n.level, []).append(n)
        for level in sorted(by_level.keys()):
            level_nodes = by_level[level]
            print(f"\n  Level {level} ({len(level_nodes)} nodes):")
            for n in level_nodes:
                pi_info = f", mapped_pi={len(n.mapped_pi_nodes) if n.mapped_pi_nodes else 0}" if n.mapped_pi_nodes else ""
                print(f"    [{n.seq_num}] {n.title}{pi_info}")

        # Check contents
        stmt_content = select(KnowledgeContent).where(
            KnowledgeContent.knowledge_node_id.in_([n.id for n in nodes])
        )
        res_content = await db.execute(stmt_content)
        contents = res_content.scalars().all()
        print(f"\nTotal KnowledgeContents: {len(contents)}")

        # Show content stats
        if contents:
            lengths = [len(c.content_md) for c in contents]
            print(f"  Content length: min={min(lengths)}, max={max(lengths)}, avg={sum(lengths)//len(lengths)}")

        # Show a few sample contents
        print("\n--- Sample Contents (first 3 leaf nodes) ---")
        leaf_nodes = [n for n in nodes if n.level == max(by_level.keys())] if by_level else []
        for n in leaf_nodes[:3]:
            node_contents = [c for c in contents if c.knowledge_node_id == n.id]
            print(f"\n  [{n.title}]")
            for c in node_contents:
                preview = c.content_md[:200].replace('\n', ' ')
                print(f"    Content ({len(c.content_md)} chars): {preview}...")

        # Final verdict
        print("\n" + "=" * 60)
        print("VERIFICATION SUMMARY")
        print("=" * 60)
        if len(nodes) > 0 and len(contents) > 0:
            print(f"SUCCESS: {len(nodes)} KnowledgeNodes and {len(contents)} KnowledgeContents created.")
            print(f"Tree structure: {len(by_level.get(1, []))} chapters, {len(by_level.get(2, []))} sections, {len(by_level.get(3, []))} concepts")
        else:
            print("FAILED: No nodes or contents were created!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
