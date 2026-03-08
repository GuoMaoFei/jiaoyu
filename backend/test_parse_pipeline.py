"""
Diagnostic script: test PageIndex + VLM pipeline on a small PDF.
Step 1: Extract first 15 pages from the full textbook into a small PDF.
Step 2: Run PageIndex on it and print the raw tree result.
Step 3: Run VLM catalog extraction and print the raw result.
"""
import os
import sys
import json
import asyncio

# Make sure we can import app modules
sys.path.insert(0, os.path.dirname(__file__))

# Load .env
from dotenv import load_dotenv
load_dotenv()

FULL_PDF = r"d:\project\python\jiaoyu_agent\jiaocai\（根据2022年版课程标准修订）义务教育教科书·语文一年级上册.pdf"
SMALL_PDF = r"d:\project\python\jiaoyu_agent\backend\test_small.pdf"
MAX_PAGES = 15


def create_small_pdf():
    """Extract first MAX_PAGES pages from the full PDF."""
    import fitz
    doc = fitz.open(FULL_PDF)
    total = len(doc)
    print(f"[INFO] Full PDF has {total} pages, extracting first {MAX_PAGES}...")

    new_doc = fitz.open()
    pages_to_copy = min(MAX_PAGES, total)
    new_doc.insert_pdf(doc, from_page=0, to_page=pages_to_copy - 1)
    new_doc.save(SMALL_PDF)
    new_doc.close()
    doc.close()

    size_mb = os.path.getsize(SMALL_PDF) / 1024 / 1024
    print(f"[INFO] Small PDF created: {SMALL_PDF} ({size_mb:.2f} MB)")
    return SMALL_PDF


def test_pageindex(pdf_path: str):
    """Run PageIndex on the PDF and return the raw tree."""
    print("\n" + "=" * 60)
    print("STEP 1: PageIndex Raw Tree")
    print("=" * 60)

    from app.config import get_settings
    settings = get_settings()

    # Set Aliyun env vars for PageIndex
    if settings.ALIYUN_API_KEY:
        os.environ["CHATGPT_API_KEY"] = settings.ALIYUN_API_KEY
        os.environ["CHATGPT_BASE_URL"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        print("[INFO] Set Aliyun API key for PageIndex")

    from pageindex.utils import ConfigLoader
    from pageindex.page_index import page_index_main

    config_loader = ConfigLoader()
    user_opt = {
        'model': 'qwen-max',
        'if_add_node_summary': 'yes',
        'if_add_doc_description': 'no',
        'if_add_node_text': 'yes',
        'if_add_node_id': 'yes'
    }
    opt = config_loader.load(user_opt)

    print(f"[INFO] Running PageIndex on {pdf_path}...")
    tree_result = page_index_main(pdf_path, opt)

    print(f"\n[RESULT] Type of tree_result: {type(tree_result)}")
    print(f"[RESULT] Raw tree_result (first 3000 chars):")
    raw_str = json.dumps(tree_result, ensure_ascii=False, indent=2)
    print(raw_str[:3000])
    if len(raw_str) > 3000:
        print(f"... (truncated, total {len(raw_str)} chars)")

    # Check top-level keys
    if isinstance(tree_result, dict):
        print(f"\n[RESULT] Top-level keys: {list(tree_result.keys())}")
        # Check the first child if it exists
        children = tree_result.get("children", [])
        if children:
            print(f"[RESULT] First child keys: {list(children[0].keys()) if isinstance(children[0], dict) else type(children[0])}")
    elif isinstance(tree_result, list):
        print(f"\n[RESULT] List length: {len(tree_result)}")
        if tree_result:
            first = tree_result[0]
            print(f"[RESULT] First item type: {type(first)}")
            if isinstance(first, dict):
                print(f"[RESULT] First item keys: {list(first.keys())}")

    return tree_result


async def test_vlm_catalog(pdf_path: str):
    """Run VLM catalog extraction and return the raw result."""
    print("\n" + "=" * 60)
    print("STEP 2: VLM Catalog Extraction")
    print("=" * 60)

    from app.utils.vlm_catalog import extract_catalog_from_pdf
    print(f"[INFO] Running VLM catalog extraction on {pdf_path}...")

    vlm_tree = await extract_catalog_from_pdf(pdf_path)

    print(f"\n[RESULT] Type of vlm_tree: {type(vlm_tree)}")
    print(f"[RESULT] Length: {len(vlm_tree) if vlm_tree else 0}")
    raw_str = json.dumps(vlm_tree, ensure_ascii=False, indent=2)
    print(f"[RESULT] Raw vlm_tree (first 3000 chars):")
    print(raw_str[:3000])
    if len(raw_str) > 3000:
        print(f"... (truncated, total {len(raw_str)} chars)")

    return vlm_tree


async def main():
    # Step 0: Create small PDF
    pdf_path = create_small_pdf()

    # Step 1: Test PageIndex
    try:
        tree_result = test_pageindex(pdf_path)
    except Exception as e:
        print(f"[ERROR] PageIndex failed: {e}")
        import traceback
        traceback.print_exc()
        tree_result = None

    # Step 2: Test VLM Catalog
    try:
        vlm_tree = await test_vlm_catalog(pdf_path)
    except Exception as e:
        print(f"[ERROR] VLM Catalog failed: {e}")
        import traceback
        traceback.print_exc()
        vlm_tree = None

    # Step 3: Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"PageIndex tree: {'OK' if tree_result else 'FAILED'}")
    print(f"VLM catalog: {'OK' if vlm_tree else 'FAILED'}")

    if tree_result:
        # Check what _parse_and_save_tree would do
        if isinstance(tree_result, dict):
            node_id = tree_result.get("node_id")
            title = tree_result.get("title", f"Node {node_id}")
            print(f"\n[SIMULATION] Root node would be saved as: title='{title}', pi_ref='{node_id}'")
        elif isinstance(tree_result, list) and tree_result:
            first = tree_result[0]
            if isinstance(first, dict):
                node_id = first.get("node_id")
                title = first.get("title", f"Node {node_id}")
                print(f"\n[SIMULATION] First root node would be saved as: title='{title}', pi_ref='{node_id}'")

    # Cleanup
    if os.path.exists(SMALL_PDF):
        os.remove(SMALL_PDF)
        print(f"\n[CLEANUP] Removed {SMALL_PDF}")


if __name__ == "__main__":
    asyncio.run(main())
