import fitz
import base64
import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from app.utils.llm_router import get_vision_model


def detect_pdf_type(pdf_path: str, sample_pages: list = None, page_list: list = None) -> str:
    """
    Detect if a PDF is a scanned (image-based) or text-based PDF.

    Detection based on:
    1. If page_list is provided (OCR results), use its characteristics
    2. Otherwise, sample text from the raw PDF

    Returns:
        "scanned": if characteristics suggest image-based PDF (OCR was needed)
        "text": if characteristics suggest text-based PDF
    """
    if page_list is not None and len(page_list) > 0:
        total_tokens = sum(p[1] for p in page_list)
        avg_tokens = total_tokens / len(page_list)

        token_diversity = 0
        for p in page_list[:10]:
            text = p[0]
            unique_chars = len(set(text))
            token_len_ratio = unique_chars / max(len(text), 1)
            token_diversity += token_len_ratio
        token_diversity /= min(len(page_list), 10)

        ocr_noise_patterns = [r'[Il1]', r'[O0]', r'■', r'●', r'▪', r'▫']
        noise_count = 0
        for p in page_list[:20]:
            text = p[0]
            for pattern in ocr_noise_patterns:
                noise_count += len(re.findall(pattern, text))

        print(f"[DEBUG] PDF type detection: avg_tokens={avg_tokens:.1f}, token_diversity={token_diversity:.3f}, noise_count={noise_count}")
        if avg_tokens > 300 and token_diversity < 0.4:
            return "scanned"
        if noise_count > 50:
            return "scanned"
        return "text"

    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    if sample_pages is None:
        sample_pages = [0, min(5, total_pages-1), min(10, total_pages-1)]

    low_text_count = 0
    for idx in sample_pages:
        if idx >= total_pages:
            continue
        page = doc.load_page(idx)
        text = page.get_text()
        clean_text = re.sub(r'\s+', '', text)
        if len(clean_text) < 100:
            low_text_count += 1

    doc.close()

    if low_text_count >= len(sample_pages) * 0.6:
        return "scanned"
    return "text"


async def extract_catalog_for_scanned_pdf(pdf_path: str, toc_page_indices: list, page_list: list) -> dict:
    """
    Extract catalog from a scanned PDF using VLM.

    1. VLM reads TOC pages to extract {title, structure, printed_page}
    2. VLM reads the last TOC page to find which printed page Chapter 1 starts at
    3. Search OCR cache for Chapter 1 to establish the offset mapping
    4. Returns catalog with physical_index format

    Args:
        pdf_path: Path to the PDF file
        toc_page_indices: List of TOC page indices (0-based) from check_toc()
        page_list: List of (ocr_text, tokens) tuples from OCR cache

    Returns:
        dict with keys:
        - toc_with_page_number: list of {structure, title, physical_index}
        - page_mapping: {printed_page: physical_page_index}
    """
    doc = fitz.open(pdf_path)

    toc_images = []
    for page_idx in toc_page_indices:
        page = doc.load_page(page_idx)
        pix = page.get_pixmap(matrix=fitz.Matrix(1, 1))
        img_bytes = pix.tobytes("png")
        base64_image = base64.b64encode(img_bytes).decode('utf-8')
        toc_images.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{base64_image}"}
        })

    images_content = [{"type": "text", "text": "These are the Table of Contents (目录) pages of a textbook."}]
    images_content.extend(toc_images)

    system_prompt = """You are an expert textbook catalog extractor for SCANNED PDFs.

Extract the complete table of contents from the images into a flat JSON array.

IMPORTANT:
1. "structure": hierarchical index like "1", "1.1", "1.2.1", etc. (use None for entries without numbers like preface or foreword)
2. "title": the chapter/section name (e.g., "第一章 总论", "第一节 会计职业道德概述"). Do NOT include trailing dots "......" or page leaders.
3. "page": the PRINTED page number shown IN THE BOOK (integer). This is NOT the physical scan page number.

Common patterns in Chinese textbooks:
- 章节目录页上: "第一章 总论 ................... 1" or "第一章 总论 .........  1"
- 页码通常在条目的右侧或底部
- Some TOC pages may have the page number at the BOTTOM of the page where Chapter 1 content starts

Return ONLY a valid JSON array (no markdown). Example:
[
    {"structure": "1", "title": "第一章 总论", "page": 1},
    {"structure": "1.1", "title": "第一节 会计职业道德概述", "page": 2},
    {"structure": "1.2", "title": "第二节 会计法规制度体系概述", "page": 4},
    ...
]

Be thorough - extract ALL chapters and sections. Include chapter-level entries (structure like "1") and all nested sections."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=images_content)
    ]

    llm = get_vision_model(temperature=0.0)

    try:
        response = await llm.ainvoke(messages)
        text_res = response.content.strip()

        if text_res.startswith("```json"):
            text_res = text_res[7:]
        if text_res.startswith("```"):
            text_res = text_res[3:]
        if text_res.endswith("```"):
            text_res = text_res[:-3]

        toc_entries = json.loads(text_res.strip())
    except Exception as e:
        print(f"Error extracting TOC via VLM: {e}")
        doc.close()
        return {"toc_with_page_number": [], "page_mapping": {}}

    chapter1_entry = None
    for entry in toc_entries:
        structure = str(entry.get("structure", ""))
        title = entry.get("title", "")
        if structure == "1" or (title and title.startswith("第一章") and not title[3:4].isdigit()):
            chapter1_entry = entry
            break

    chapter1_printed_page = chapter1_entry.get("page") if chapter1_entry else None
    print(f"[VLM] Chapter 1 printed page from VLM: {chapter1_printed_page}")

    chapter1_physical_idx = None
    if chapter1_printed_page is not None:
        chapter1_patterns = [
            rf"第[一二三四五六七八九十零]+章\s*总\s*论",
            rf"第一章\s*总\s*论",
            rf"^1\s*总\s*论",
        ]
        for i, (page_text, _) in enumerate(page_list):
            text_clean = re.sub(r'\s+', '', page_text)
            for pattern in chapter1_patterns:
                if re.search(pattern, text_clean):
                    chapter1_physical_idx = i + 1
                    print(f"[VLM] Found Chapter 1 at physical page {chapter1_physical_idx} (OCR page index {i})")
                    break
            if chapter1_physical_idx:
                break

    page_mapping = {}
    if chapter1_printed_page is not None and chapter1_physical_idx is not None:
        offset = chapter1_physical_idx - chapter1_printed_page
        print(f"[VLM] Page offset: {offset} (physical_idx={chapter1_physical_idx} - printed_page={chapter1_printed_page})")
        for entry in toc_entries:
            printed_page = entry.get("page")
            if printed_page is not None:
                physical_index = printed_page + offset
                physical_index = max(1, min(physical_index, len(page_list)))
                page_mapping[printed_page] = physical_index
                entry["physical_index"] = f"<physical_index_{physical_index}>"
            else:
                entry["physical_index"] = None
    else:
        print(f"[VLM] Could not establish page mapping: chapter1_printed_page={chapter1_printed_page}, chapter1_physical_idx={chapter1_physical_idx}")
        for entry in toc_entries:
            entry["physical_index"] = None

    result = {
        "toc_with_page_number": [
            {"structure": e.get("structure"), "title": e.get("title"), "physical_index": e.get("physical_index")}
            for e in toc_entries
        ],
        "page_mapping": page_mapping
    }

    doc.close()
    return result

async def extract_catalog_from_pdf(pdf_path: str, max_pages: int = 15) -> list:
    """
    Extracts the table of contents from the first `max_pages` of a PDF
    using a Vision Large Language Model (VLM).
    Returns a structured JSON tree.
    """
    doc = fitz.open(pdf_path)
    # Get up to the first max_pages
    pages_to_process = min(max_pages, len(doc))
    
    images_content = []
    
    for page_num in range(pages_to_process):
        page = doc.load_page(page_num)
        # Render the page to a pixmap (image)
        pix = page.get_pixmap(matrix=fitz.Matrix(1, 1))  # 1x scale to reduce base64 HTTP payload size
        
        # Get raw image bytes in PNG format
        img_bytes = pix.tobytes("png")
        
        # Encode to base64
        base64_image = base64.b64encode(img_bytes).decode('utf-8')
        
        # Determine if we should only send pages that look like a catalog? 
        # For simplicity, we send all first N pages. The VLM is smart enough to find the catalog.
        
        images_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{base64_image}"
            }
        })
        
    doc.close()
    
    # Construct the Prompt
    system_prompt = """You are an expert textbook catalog extractor. 
Analyze the provided images of the first few pages of a textbook. 
Find the Table of Contents (目录) and extract it accurately into a nested JSON array of objects.
Do not extract introductory texts or prefaces unless they are explicitly listed as chapters in the TOC.
Each object must have:
- "title": The name of the chapter/section/concept (e.g., "第一单元 识字" or "1 天地人"). Do not include trailing dot leaders (......).
- "page": The start page number if visible (integer), otherwise null.
- "children": A list of sub-sections (same structure), or an empty list if there are none.

RETURN ONLY VALID JSON. No markdown wrappings like ```json.
"""

    human_content = [{"type": "text", "text": "Extract the hierarchical TOC from these pages as JSON."}]
    human_content.extend(images_content)
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_content)
    ]
    
    llm = get_vision_model(temperature=0.0)
    
    try:
        response = await llm.ainvoke(messages)
        text_res = response.content.strip()
        
        # Strip potential markdown code blocks
        if text_res.startswith("```json"):
            text_res = text_res[7:]
        if text_res.startswith("```"):
            text_res = text_res[3:]
        if text_res.endswith("```"):
            text_res = text_res[:-3]
            
        return json.loads(text_res.strip())
    except Exception as e:
        print(f"Error extracting visual catalog: {e}")
        # In actual usage, fallback to an empty list or raise
        return []

def _flatten_pi_tree(pi_node, result_list):
    """Recursively flattens the PageIndex tree to extract node_id and summaries."""
    if isinstance(pi_node, list):
        for child in pi_node:
            _flatten_pi_tree(child, result_list)
        return
        
    node_id = pi_node.get("node_id")
    summary = pi_node.get("summary", "")
    title = pi_node.get("title", "")
    if node_id:
        result_list.append({"node_id": node_id, "title": title, "summary": summary})
        
    for child in pi_node.get("children", []):
        _flatten_pi_tree(child, result_list)

async def map_dual_tree(vlm_tree: list, pi_tree: list | dict) -> list:
    """
    Takes the VLM-generated visual TOC and the PageIndex generated raw tree.
    Uses an LLM to map the PageIndex node_ids to the VLM TOC nodes.
    Injects a 'mapped_pi_nodes' list into each VLM node.
    """
    if not vlm_tree:
        return []
        
    from app.utils.llm_router import get_fast_model
    
    # Flatten the PI Tree
    flat_pi_nodes = []
    _flatten_pi_tree(pi_tree, flat_pi_nodes)
    
    # We don't want to overwhelm the context if the PI tree is massive, but for 
    # a textbook chapter or a typical book, it usually fits in an LLM context.
    # We will format it concisely.
    pi_nodes_str = "\n".join([f"ID: {n['node_id']} | Title: {n['title']} | Summary: {n['summary'][:150]}..." for n in flat_pi_nodes])
    
    system_prompt = f"""You are an intelligent Dual-Tree mapping engine.
You will be provided with:
1. A visual Table of Contents (VLM Tree) representing the perfect human-readable chapters.
2. A list of raw knowledge blocks extracted by a system (PI Nodes).

Your task is to assign the relevant PI Node IDs to the corresponding VLM Tree nodes based on semantic similarity and context.
You must return the EXACT SAME VLM Tree JSON structure, but add a new field "mapped_pi_nodes" (a list of string IDs) to EVERY node in the VLM Tree.
It's okay if multiple VLM nodes map to the same PI node, or if some PI nodes are not mapped. A leaf concept node usually maps to 1-3 PI nodes.

Available PI Nodes:
{pi_nodes_str}

RETURN ONLY VALID JSON. The output must be the literal JSON array mirroring the VLM Tree, but with "mapped_pi_nodes" injected. DO NOT wrap with Markdown (```json)."""

    human_content = json.dumps(vlm_tree, ensure_ascii=False, indent=2)
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_content)
    ]
    
    llm = get_fast_model(temperature=0.0)
    
    try:
        response = await llm.ainvoke(messages)
        text_res = response.content.strip()
        
        if text_res.startswith("```json"):
            text_res = text_res[7:]
        if text_res.startswith("```"):
            text_res = text_res[3:]
        if text_res.endswith("```"):
            text_res = text_res[:-3]
            
        return json.loads(text_res.strip())
    except Exception as e:
        print(f"Error mapping dual tree: {e}")
        # Return the original tree without mapping if it fails
        return vlm_tree


