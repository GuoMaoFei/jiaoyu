import fitz  # PyMuPDF
import base64
import json
from langchain_core.messages import HumanMessage, SystemMessage
from app.utils.llm_router import get_vision_model

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


