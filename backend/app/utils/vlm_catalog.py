import fitz
import base64
import json
import re
import logging
from typing import List, Tuple, Optional, Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from app.utils.llm_router import get_vision_model

logger = logging.getLogger(__name__)


def _extract_bigrams_for_mapping(text: str) -> set:
    """Extract character bigrams from text for Jaccard similarity computation.

    Reuses the _extract_bigrams from candidate_filter if available,
    otherwise implements a simple version locally.
    """
    try:
        from app.agent.tools.candidate_filter import _extract_bigrams
        bigram_counter = _extract_bigrams(text)
        return set(bigram_counter.elements())
    except ImportError:
        pass

    # Fallback: simple bigram implementation
    _CJK_PUNCT_RE = re.compile(r'[\s\u3000-\u303f\uff00-\uffef\u2000-\u206f]')
    cleaned = _CJK_PUNCT_RE.sub('', text.lower())
    if len(cleaned) < 2:
        return set()
    return {cleaned[i:i+2] for i in range(len(cleaned) - 1)}


def _jaccard_bigram_similarity(text_a: str, text_b: str) -> float:
    """Compute Jaccard similarity between two strings using bigram sets."""
    set_a = _extract_bigrams_for_mapping(text_a)
    set_b = _extract_bigrams_for_mapping(text_b)
    if not set_a and not set_b:
        return 0.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _extract_anchor_keywords(title: str) -> list:
    """Extract searchable keyword fragments from a chapter title for OCR text matching."""
    keywords = []
    title = title.strip()

    m = re.match(r"第[一二三四五六七八九十零百]+[章节单元课组]", title)
    if m:
        keywords.append(re.sub(r'\s+', '', title))
        remainder = title[m.end():].strip()
        if remainder:
            core = remainder[:min(len(remainder), 8)]
            keywords.append(re.sub(r'\s+', '', core))

    if not keywords:
        clean = re.sub(r'\s+', '', title)
        keywords.append(clean[:min(len(clean), 10)])

    return keywords


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
        if noise_count > 50 and avg_tokens < 300:
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
        pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
        img_bytes = pix.tobytes("jpeg", jpg_quality=60)
        base64_image = base64.b64encode(img_bytes).decode('utf-8')
        toc_images.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
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

    anchor_entries = []
    for entry in toc_entries:
        structure = str(entry.get("structure", "") or "")
        title = str(entry.get("title", "") or "")
        page = entry.get("page")
        if page is None or not title:
            continue
        is_chapter = (
            structure in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10")
            or re.match(r"^第[一二三四五六七八九十零]+章", title)
        )
        if is_chapter:
            anchor_entries.append(entry)
        elif not anchor_entries:
            anchor_entries.append(entry)

    best_offset = None
    best_anchor_title = None
    for anchor in anchor_entries:
        anchor_title = str(anchor.get("title", ""))
        anchor_page = anchor.get("page")
        if anchor_page is None:
            continue

        anchor_keywords = _extract_anchor_keywords(anchor_title)
        if not anchor_keywords:
            continue

        for i, (page_text, _) in enumerate(page_list):
            text_clean = re.sub(r'\s+', '', page_text)
            for kw in anchor_keywords:
                if kw in text_clean:
                    physical_idx = i + 1
                    offset = physical_idx - anchor_page
                    print(f"[VLM] Anchor '{anchor_title}' at physical={physical_idx}, printed={anchor_page}, offset={offset}")
                    best_offset = offset
                    best_anchor_title = anchor_title
                    break
            if best_offset is not None:
                break
        if best_offset is not None:
            break

    page_mapping = {}
    if best_offset is not None:
        print(f"[VLM] Using offset={best_offset} from anchor '{best_anchor_title}'")
        for entry in toc_entries:
            printed_page = entry.get("page")
            if printed_page is not None:
                physical_index = printed_page + best_offset
                physical_index = max(1, min(physical_index, len(page_list)))
                page_mapping[printed_page] = physical_index
                entry["physical_index"] = f"<physical_index_{physical_index}>"
            else:
                entry["physical_index"] = None
    else:
        print(f"[VLM] Could not establish page mapping: no anchor found in OCR text")
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


async def extract_catalog_from_pdf(
    pdf_path: str,
    max_pages: int = 8,
    page_list: Optional[List[Tuple[str, int]]] = None,
) -> list:
    """
    从 PDF 提取目录，优先使用缓存的 page_list（规则化解析），
    失败时 fallback 到 VLM 图片提取。

    Args:
        pdf_path: PDF 文件路径（仅 VLM fallback 时使用）
        max_pages: VLM fallback 时处理的页数
        page_list: 缓存的逐页文本 [(text, tokens), ...]，优先使用

    Returns:
        层级目录树 [{title, page, children}, ...]
    """
    # 优先: 从缓存的 page_list 规则化解析
    if page_list:
        catalog = extract_catalog_from_page_list(page_list)
        if catalog:
            logger.info("[Catalog] 从缓存 page_list 规则化解析成功，跳过 VLM")
            return catalog
        logger.info("[Catalog] 规则化解析未成功，fallback 到 VLM")

    # Fallback: VLM 图片提取
    logger.info(f"[Catalog] 使用 VLM 从 PDF 图片提取目录 (max_pages={max_pages})")
    doc = fitz.open(pdf_path)
    pages_to_process = min(max_pages, len(doc))

    images_content = []

    for page_num in range(pages_to_process):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))

        img_bytes = pix.tobytes("jpeg", jpg_quality=60)

        base64_image = base64.b64encode(img_bytes).decode('utf-8')

        images_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_image}"
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


def extract_catalog_from_page_list(
    page_list: List[Tuple[str, int]],
    toc_page_indices: Optional[List[int]] = None,
) -> list:
    """
    从缓存的 page_list 中提取目录，优先使用规则化解析，无需 VLM。

    流程:
    1. 如果提供了 toc_page_indices，从指定页提取目录文本
    2. 否则自动检测目录页
    3. 先尝试规则化解析（正则匹配章节编号+标题+页码）
    4. 规则化失败则返回空列表，由调用方 fallback 到 LLM

    Args:
        page_list: [(text, tokens), ...] 缓存的逐页文本
        toc_page_indices: 目录页索引（0-based），None 则自动检测

    Returns:
        层级目录树 [{title, page, children}, ...]
    """
    # 1. 确定目录页
    if toc_page_indices is None:
        toc_page_indices = _detect_toc_pages(page_list)

    if not toc_page_indices:
        logger.info("[Catalog] 未检测到目录页")
        return []

    # 2. 拼接目录文本
    toc_text_parts = []
    for idx in toc_page_indices:
        if 0 <= idx < len(page_list):
            toc_text_parts.append(page_list[idx][0])
    toc_text = "\n".join(toc_text_parts)

    if not toc_text.strip():
        logger.info("[Catalog] 目录页文本为空")
        return []

    logger.info(f"[Catalog] 从 {len(toc_page_indices)} 个目录页提取到 {len(toc_text)} 字符")

    # 3. 规则化解析
    entries = _parse_toc_text_rule_based(toc_text)

    if not entries:
        logger.info("[Catalog] 规则化解析未提取到条目，将 fallback 到 LLM")
        return []

    # 4. 构建层级树
    tree = _build_toc_tree(entries)
    logger.info(f"[Catalog] 规则化解析成功: {len(entries)} 条目, {len(tree)} 根节点")
    return tree


def _detect_toc_pages(page_list: List[Tuple[str, int]]) -> List[int]:
    """规则化检测目录页索引。"""
    toc_keywords = ["目录", "目  录", "目次", "CONTENTS", "Contents", "contents"]
    toc_pages = []

    for i, (text, _) in enumerate(page_list):
        if i >= 20:  # 只在前20页搜索
            break
        for kw in toc_keywords:
            if kw in text:
                # 目录页通常包含章节条目模式
                has_toc_pattern = bool(
                    re.search(r'第[一二三四五六七八九十]+[章节单元]', text)
                    or re.search(r'\.{3,}\s*\d+', text)
                    or re.search(r'\d+\.\d+', text)
                )
                if has_toc_pattern or len(text) < 2000:
                    toc_pages.append(i)
                break

    return toc_pages


def _parse_toc_text_rule_based(toc_text: str) -> List[dict]:
    """
    规则化解析目录文本，提取 [{structure, title, page}, ...]。

    支持的模式:
    - "第一章 标题 ... 1" / "第1节 标题 ... 12"
    - "1.1 标题 ... 12" / "1.1.1 标题 ... 15"
    - "第一单元 标题" / "第二课 标题"
    - 缩进表示层级
    """
    entries = []
    lines = toc_text.split('\n')

    # 中文数字映射
    cn_num_map = {
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
        '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20,
        '零': 0,
    }

    def _cn_to_int(cn: str) -> int:
        """中文数字转整数（简单版，支持1-99）。"""
        cn = cn.strip()
        if cn in cn_num_map:
            return cn_num_map[cn]
        # 尝试解析 "二十三" 这类
        if '十' in cn:
            parts = cn.split('十')
            tens = cn_num_map.get(parts[0], 1) if parts[0] else 1
            ones = cn_num_map.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
            return tens * 10 + ones
        return 0

    # 模式1: "第X章/节/单元/课 标题 [....] 页码"
    pattern_chapter = re.compile(
        r'第([一二三四五六七八九十零百\d]+)[章节单元课组]\s+(.+?)(?:\s*[\.…·…—─\-]+\s*(\d+))?\s*$'
    )
    # 模式2: "1.1.1 标题 [....] 页码" 或 "1 标题 [....] 页码"
    pattern_numbered = re.compile(
        r'^(\d+(?:\.\d+)*)\s+(.+?)(?:\s*[\.…·…—─\-]+\s*(\d+))?\s*$'
    )
    # 模式3: 行尾页码 "标题 .... 12" 或 "标题 12"
    pattern_page_trailing = re.compile(
        r'(.+?)\s*[\.…·…—─\-]+\s*(\d+)\s*$'
    )

    for line in lines:
        line = line.strip()
        if not line or len(line) < 2:
            continue

        # 去除常见的PDF提取噪声
        line = re.sub(r'\s+', ' ', line)

        entry = None

        # 尝试模式1: 第X章/节
        m = pattern_chapter.match(line)
        if m:
            num_str, title, page = m.group(1), m.group(2).strip(), m.group(3)
            num = _cn_to_int(num_str) if not num_str.isdigit() else int(num_str)
            # 判断层级: "第X章" = level 1, "第X节" = level 2
            level_keyword = re.search(r'第[一二三四五六七八九十零百\d]+([章节单元课组])', line)
            if level_keyword:
                kw = level_keyword.group(1)
                if kw in ('章', '单元'):
                    structure = str(num)
                elif kw in ('节', '课', '组'):
                    structure = f"x.{num}"  # x 表示待定父章节
                else:
                    structure = str(num)
            else:
                structure = str(num)

            title = re.sub(r'[\.…·…—─\-]+', '', title).strip()
            entry = {
                "structure": structure,
                "title": title,
                "page": int(page) if page else None,
            }

        # 尝试模式2: 数字编号
        if entry is None:
            m = pattern_numbered.match(line)
            if m:
                structure, title, page = m.group(1), m.group(2).strip(), m.group(3)
                title = re.sub(r'[\.…·…—─\-]+', '', title).strip()
                entry = {
                    "structure": structure,
                    "title": title,
                    "page": int(page) if page else None,
                }

        # 尝试模式3: 仅提取行尾页码
        if entry is None:
            m = pattern_page_trailing.match(line)
            if m and len(m.group(1).strip()) > 1:
                title, page = m.group(1).strip(), m.group(2)
                # 排除纯数字行
                if not title.isdigit():
                    entry = {
                        "structure": None,
                        "title": title,
                        "page": int(page),
                    }

        if entry:
            entries.append(entry)

    return entries


def _build_toc_tree(entries: List[dict]) -> List[dict]:
    """
    将扁平的目录条目列表构建为层级树。

    根据 structure 字段判断层级关系:
    - "1", "2" → 根节点
    - "1.1", "1.2" → "1" 的子节点
    - "1.1.1" → "1.1" 的子节点
    - "x.3" (节) → 挂到最近的章节点下
    - None → 挂到当前最近的父节点下
    """
    if not entries:
        return []

    tree = []  # 根节点列表
    stack = []  # (structure_path, node) 栈，追踪当前路径

    for entry in entries:
        structure = entry.get("structure")
        title = entry.get("title", "")
        page = entry.get("page")

        node = {"title": title, "page": page, "children": []}

        if structure is None:
            # 无编号条目，挂到栈顶或根
            if stack:
                stack[-1][1]["children"].append(node)
            else:
                tree.append(node)
            continue

        # 解析 structure 层级深度
        if structure.startswith("x."):
            # "x.3" 表示节，挂到最近的章节点
            if stack:
                # 找到最近的 level-1 节点
                for i in range(len(stack) - 1, -1, -1):
                    path = stack[i][0]
                    if '.' not in path:
                        stack[i][1]["children"].append(node)
                        stack.append((f"{path}.{structure[2:]}", node))
                        break
                else:
                    tree.append(node)
            else:
                tree.append(node)
            continue

        parts = structure.split('.')
        depth = len(parts)

        # 弹出栈中深度 >= 当前深度的节点
        while stack and len(stack[-1][0].split('.')) >= depth:
            stack.pop()

        if stack:
            stack[-1][1]["children"].append(node)
        else:
            tree.append(node)

        stack.append((structure, node))

    return tree


async def extract_catalog_from_text(toc_text: str) -> list:
    """Parse raw TOC text into a hierarchical JSON tree using a text-only LLM."""
    if not toc_text or not toc_text.strip():
        return []

    from app.utils.llm_router import get_fast_model

    system_prompt = """你是一个专业的教材目录解析器。
将提供的目录文本解析为层级 JSON 数组。

每个对象包含:
- "title": 章节标题（不含前导点和页码）
- "page": 起始页码（整数或 null）
- "children": 子节点列表（同结构，无子节点则为空列表）

根据缩进、层级编号（如 1.1, 1.2）、章节名称语义（如"第X单元"包含课文）判断父子关系。

只返回合法 JSON，不要 markdown 代码块。"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"目录文本:\n\n{toc_text}"),
    ]

    llm = get_fast_model(temperature=0.0)

    try:
        response = await llm.ainvoke(messages)
        text_res = response.content.strip()

        for prefix in ("```json", "```"):
            if text_res.startswith(prefix):
                text_res = text_res[len(prefix):]
        if text_res.endswith("```"):
            text_res = text_res[:-3]

        result = json.loads(text_res.strip())
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            for key in ("table_of_contents", "toc", "items", "entries"):
                if key in result and isinstance(result[key], list):
                    return result[key]
        return []
    except Exception as e:
        print(f"Error extracting catalog from text: {e}")
        return []


def _flatten_pi_tree(pi_node, result_list):
    """Recursively flattens the PageIndex tree to extract node_id, summaries, and page info."""
    if isinstance(pi_node, list):
        for child in pi_node:
            _flatten_pi_tree(child, result_list)
        return

    node_id = pi_node.get("node_id")
    summary = pi_node.get("summary", "")
    title = pi_node.get("title", "")
    if node_id:
        entry = {"node_id": node_id, "title": title, "summary": summary}
        for key in ("physical_index", "start_index", "end_index", "page"):
            val = pi_node.get(key)
            if val is not None:
                entry[key] = val
        result_list.append(entry)

    children = pi_node.get("nodes", pi_node.get("children", []))
    for child in children:
        _flatten_pi_tree(child, result_list)


def _get_leaf_catalog_nodes(tree: list) -> list:
    """Collect all leaf nodes from the catalog tree in order."""
    leaves = []
    for node in tree:
        children = node.get("children", [])
        if children:
            leaves.extend(_get_leaf_catalog_nodes(children))
        else:
            leaves.append(node)
    return leaves


def _get_all_catalog_nodes_flat(tree: list, result: list = None) -> list:
    """Collect all catalog nodes in depth-first order with their page info."""
    if result is None:
        result = []
    for node in tree:
        result.append(node)
        for child in node.get("children", []):
            _get_all_catalog_nodes_flat([child], result)
    return result


def _build_page_range_map(catalog_nodes: list, pi_nodes: list, total_pi_pages: int) -> dict:
    """Build a mapping from catalog node title -> set of allowed PI node_id strings.

    Uses catalog 'page' numbers and PI node 'physical_index' to constrain which
    PI nodes can belong to which catalog entry.
    """
    catalog_pages = []
    for node in catalog_nodes:
        page = node.get("page")
        if page is not None:
            catalog_pages.append((node, page))

    if len(catalog_pages) < 2:
        return {}

    catalog_pages.sort(key=lambda x: x[1])

    pi_by_page = {}
    for pn in pi_nodes:
        pi_page = pn.get("physical_index") or pn.get("start_index")
        if pi_page is not None:
            pi_by_page.setdefault(int(pi_page), []).append(pn["node_id"])

    page_range_map = {}
    for idx, (node, page) in enumerate(catalog_pages):
        start = page
        end = catalog_pages[idx + 1][1] - 1 if idx + 1 < len(catalog_pages) else total_pi_pages
        allowed_ids = set()
        for p in range(start, end + 1):
            allowed_ids.update(pi_by_page.get(p, []))
        page_range_map[id(node)] = allowed_ids

    return page_range_map


async def map_dual_tree(vlm_tree: list, pi_tree: list | dict) -> list:
    """
    Takes the VLM/text-generated catalog TOC and the PageIndex raw tree.
    Uses an LLM to map the PageIndex node_ids to the catalog nodes.
    Injects a 'mapped_pi_nodes' list into each catalog node.
    """
    if not vlm_tree:
        return []

    from app.utils.llm_router import get_fast_model

    flat_pi_nodes = []
    _flatten_pi_tree(pi_tree, flat_pi_nodes)

    if not flat_pi_nodes:
        return vlm_tree

    all_catalog_nodes = _get_all_catalog_nodes_flat(vlm_tree)
    total_pi_pages = max(
        (n.get("physical_index") or n.get("end_index") or 0 for n in flat_pi_nodes),
        default=0,
    )

    page_range_map = _build_page_range_map(all_catalog_nodes, flat_pi_nodes, total_pi_pages)

    pi_nodes_str = "\n".join([
        f"ID: {n['node_id']} | Title: {n['title']} | Page: {n.get('physical_index') or n.get('start_index') or '?'} | Summary: {n['summary'][:100]}..."
        for n in flat_pi_nodes
    ])

    page_constraint_hint = ""
    if page_range_map:
        page_constraint_hint = (
            "\nIMPORTANT PAGE CONSTRAINTS:\n"
            "- Each PI node has a Page number (its physical position in the PDF).\n"
            "- Each catalog entry has a 'page' field (the printed page number in the book).\n"
            "- A PI node should ONLY be mapped to the catalog entry whose page range contains the PI node's page number.\n"
            "- Do NOT dump unmapped PI nodes into the last entry. If a PI node doesn't match any entry semantically, leave it unmapped (empty list).\n"
            "- The mapping must respect the sequential order: PI nodes appearing between catalog entry A and B should map to A or its children, not to entries after B.\n"
        )

    system_prompt = f"""You are an intelligent Dual-Tree mapping engine.
You will be provided with:
1. A hierarchical Table of Contents (Catalog Tree) representing the book's chapter structure.
2. A list of raw knowledge blocks extracted by a system (PI Nodes), each with a Page number.

Your task is to assign the relevant PI Node IDs to the corresponding Catalog Tree nodes based on semantic similarity AND page position.
You must return the EXACT SAME Catalog Tree JSON structure, but add a new field "mapped_pi_nodes" (a list of string IDs) to EVERY node.
{page_constraint_hint}
Rules:
- A leaf concept node usually maps to 1-3 PI nodes.
- It's okay if some PI nodes are not mapped (use empty list []).
- Do NOT map a PI node to an entry if its page number is outside that entry's range.
- Parent nodes should NOT duplicate PI nodes already mapped to their children.

Available PI Nodes:
{pi_nodes_str}

RETURN ONLY VALID JSON. The output must be the literal JSON array mirroring the Catalog Tree, but with "mapped_pi_nodes" injected into EVERY node. DO NOT wrap with Markdown. NO extra text."""

    human_content = json.dumps(vlm_tree, ensure_ascii=False, indent=2)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_content),
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

        result = json.loads(text_res.strip())

        if page_range_map:
            result = _enforce_page_constraints(result, flat_pi_nodes, page_range_map)

        return result
    except Exception as e:
        print(f"Error mapping dual tree: {e}")
        return vlm_tree


def _enforce_page_constraints(
    mapped_tree: list, pi_nodes: list, page_range_map: dict,
) -> list:
    """Post-process: remove PI node mappings that violate page range constraints."""

    pi_id_to_page = {}
    for pn in pi_nodes:
        pi_page = pn.get("physical_index") or pn.get("start_index")
        if pi_page is not None:
            pi_id_to_page[pn["node_id"]] = int(pi_page)

    def _clean_node(node: dict) -> dict:
        node_id = id(node)
        allowed = page_range_map.get(node_id)

        mapped = node.get("mapped_pi_nodes", [])
        if allowed is not None and mapped:
            cleaned = []
            for pid in mapped:
                pi_page = pi_id_to_page.get(pid)
                if pi_page is not None and allowed and pid not in allowed:
                    print(f"[PAGE-CONSTRAINT] Removing PI {pid} (page {pi_page}) from '{node.get('title', '?')}' — outside allowed range")
                    continue
                cleaned.append(pid)
            node["mapped_pi_nodes"] = cleaned

        for child in node.get("children", []):
            _clean_node(child)
        return node

    if isinstance(mapped_tree, list):
        for node in mapped_tree:
            _clean_node(node)
    return mapped_tree


def map_dual_tree_rule_based(
    catalog_tree: list,
    pi_tree: list | dict,
    coverage_threshold: float = 0.8,
) -> Tuple[list, float]:
    """规则化双树映射：基于页码范围 + 标题 Jaccard bigram 相似度，
    将 PageIndex 节点映射到 catalog 节点，零 LLM 调用。

    Args:
        catalog_tree: 层级目录树 [{title, page, children}, ...]
        pi_tree: PageIndex 树（list 或 dict）
        coverage_threshold: 覆盖率阈值（仅用于信息提示，不影响返回值）

    Returns:
        (mapped_tree, coverage)
        - mapped_tree: 与 catalog_tree 同结构，每个节点增加 mapped_pi_nodes 字段
        - coverage: 已映射 PI 节点数 / 总 PI 节点数
    """
    if not catalog_tree:
        return ([], 0.0)

    # 1. 扁平化 pi_tree
    flat_pi_nodes: List[Dict[str, Any]] = []
    _flatten_pi_tree(pi_tree, flat_pi_nodes)

    if not flat_pi_nodes:
        return (catalog_tree, 0.0)

    total_pi_count = len(flat_pi_nodes)

    # 2. 构建页码范围映射
    all_catalog_nodes = _get_all_catalog_nodes_flat(catalog_tree)
    total_pi_pages = max(
        (n.get("physical_index") or n.get("end_index") or 0 for n in flat_pi_nodes),
        default=0,
    )
    page_range_map = _build_page_range_map(all_catalog_nodes, flat_pi_nodes, total_pi_pages)

    # 3. 构建 PI node_id -> page 的快速查找
    pi_id_to_page: Dict[str, int] = {}
    for pn in flat_pi_nodes:
        pi_page = pn.get("physical_index") or pn.get("start_index")
        if pi_page is not None:
            pi_id_to_page[pn["node_id"]] = int(pi_page)

    # 4. 估算 catalog 页码到物理页的 offset
    #    尝试通过匹配 catalog 的 page 与 PI 的 physical_index 来估算 offset
    offset = _estimate_page_offset(catalog_tree, flat_pi_nodes)

    # 5. 递归映射
    mapped_pi_ids: set = set()  # 追踪已映射的 PI node_id

    def _map_node(catalog_node: Dict[str, Any]) -> Dict[str, Any]:
        """递归映射单个 catalog 节点。"""
        title = catalog_node.get("title", "")
        page = catalog_node.get("page")
        children = catalog_node.get("children", [])

        # 估算该 catalog 节点对应的物理页范围
        physical_page = None
        if page is not None and offset is not None:
            physical_page = page + offset

        # 筛选页码范围内的 PI 节点
        allowed_pi_ids = page_range_map.get(id(catalog_node))

        candidate_pi_nodes = []
        for pn in flat_pi_nodes:
            # 如果有页码范围约束，优先使用
            if allowed_pi_ids is not None:
                if pn["node_id"] not in allowed_pi_ids:
                    continue
            else:
                # 没有页码范围映射时，用 physical_page 做粗筛
                if physical_page is not None:
                    pi_page = pi_id_to_page.get(pn["node_id"])
                    if pi_page is not None and abs(pi_page - physical_page) > 20:
                        continue

            # 计算标题 Jaccard bigram 相似度
            pi_title = pn.get("title", "")
            similarity = _jaccard_bigram_similarity(title, pi_title)
            if similarity > 0.3:
                candidate_pi_nodes.append((similarity, pn))

        # 按相似度降序排列，取 top 匹配
        candidate_pi_nodes.sort(key=lambda x: x[0], reverse=True)
        mapped_ids = [pn["node_id"] for _, pn in candidate_pi_nodes]
        mapped_pi_ids.update(mapped_ids)

        # 递归处理 children
        mapped_children = [_map_node(child) for child in children]

        return {
            **catalog_node,
            "mapped_pi_nodes": mapped_ids,
            "children": mapped_children,
        }

    mapped_tree = [_map_node(node) for node in catalog_tree]

    # 6. 计算覆盖率
    coverage = len(mapped_pi_ids) / total_pi_count if total_pi_count > 0 else 0.0

    return (mapped_tree, coverage)


def _estimate_page_offset(
    catalog_tree: list,
    flat_pi_nodes: List[Dict[str, Any]],
) -> Optional[int]:
    """估算 catalog 的 page 字段到 PI physical_index 的偏移量。

    通过找到 catalog 节点 page 与 PI 节点 physical_index 的最佳对齐来估算。
    """
    # 收集 catalog 中所有有 page 的节点
    catalog_pages = []
    _collect_catalog_pages(catalog_tree, catalog_pages)
    if not catalog_pages:
        return None

    # 收集 PI 中所有 physical_index
    pi_pages = set()
    for pn in flat_pi_nodes:
        pi_page = pn.get("physical_index") or pn.get("start_index")
        if pi_page is not None:
            pi_pages.add(int(pi_page))
    if not pi_pages:
        return None

    # 尝试不同的 offset，找到使最多 catalog page 对齐到 PI page 的 offset
    pi_pages_sorted = sorted(pi_pages)
    best_offset = None
    best_match_count = 0

    # 只尝试合理的 offset 范围
    for cp in catalog_pages[:10]:  # 只用前10个catalog page来估算
        for pp in pi_pages_sorted[:20]:  # 只用前20个PI page
            candidate_offset = pp - cp
            # 计算这个 offset 下有多少 catalog page 能对齐到 PI page
            match_count = 0
            for cp2 in catalog_pages:
                estimated = cp2 + candidate_offset
                if estimated in pi_pages:
                    match_count += 1
            if match_count > best_match_count:
                best_match_count = match_count
                best_offset = candidate_offset

    # 至少要有2个对齐才认为 offset 有效
    if best_match_count >= 2:
        return best_offset
    return None


def _collect_catalog_pages(tree: list, result: list) -> None:
    """递归收集 catalog 树中所有有 page 值的节点页码。"""
    for node in tree:
        page = node.get("page")
        if page is not None and isinstance(page, (int, float)):
            result.append(int(page))
        for child in node.get("children", []):
            _collect_catalog_pages([child], result)
