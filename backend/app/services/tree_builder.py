import os
import json
import requests
import asyncio
import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config import get_settings
from app.models.material import Material, KnowledgeNode
from app.services.pdf_text_extractor import PdfTextExtractor

logger = logging.getLogger(__name__)


# ── Sentinel returned by build_catalog_from_pageindex when structure is too
#    sparse but toc_text is available — caller should use extract_catalog_from_text.
_NEED_TOC_TEXT_PARSE = object()


def build_catalog_from_pageindex(
    tree_result: Dict[str, Any],
    page_list: List[Tuple[str, int]],
) -> list:
    """从 PageIndex 结果复用构建 catalog_tree，零 LLM 调用。

    Args:
        tree_result: page_index_main 的返回结果（dict）
        page_list: 缓存的逐页文本 [(text, tokens), ...]

    Returns:
        catalog_tree: 层级目录树 [{title, page, children}, ...]
        若 structure 节点数 < 5 但有 toc_text，返回 _NEED_TOC_TEXT_PARSE 标记
        否则返回空列表
    """
    if not isinstance(tree_result, dict):
        return []

    structure = tree_result.get("structure", [])
    if not isinstance(structure, list):
        return []

    # 递归将 PageIndex 节点转为 catalog 格式
    def _convert_node(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(node, dict):
            return None
        title = node.get("title", "")
        physical_index = node.get("physical_index")
        # PageIndex 子节点在 "nodes" 或 "children" 字段
        children_raw = node.get("nodes", node.get("children", []))
        children = []
        for child in children_raw:
            converted = _convert_node(child)
            if converted is not None:
                children.append(converted)
        return {
            "title": title,
            "page": physical_index,
            "children": children,
        }

    if len(structure) >= 5:
        # 足够多的节点，直接递归构建
        # Sort by physical_index to ensure correct order
        structure_sorted = sorted(structure, key=lambda n: n.get("physical_index") or n.get("start_index") or 0)
        catalog_tree = []
        for node in structure_sorted:
            converted = _convert_node(node)
            if converted is not None:
                catalog_tree.append(converted)
        return catalog_tree

    # 节点数 < 5，检查是否有 toc_text 可用
    if len(structure) < 5:
        toc_text = tree_result.get("toc_text")
        if toc_text and isinstance(toc_text, str) and toc_text.strip():
            return _NEED_TOC_TEXT_PARSE

    return []


def _clean_title(title: str) -> str:
    """Clean abnormal spaces in titles extracted from PDF text.

    PDF text extraction often inserts spaces between characters that
    should be adjacent (e.g., "必 修" -> "必修", "语 文" -> "语文").
    This function collapses such intra-word spaces while preserving
    intentional word boundaries.
    """
    import re
    # Collapse multiple spaces into one
    cleaned = re.sub(r' {2,}', ' ', title)
    # Remove spaces between CJK characters (Chinese/Japanese/Korean)
    # CJK Unified Ideographs: U+4E00-U+9FFF
    cleaned = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', cleaned)
    # Remove space between CJK char and CJK punctuation
    cleaned = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u3000-\u303f\uff00-\uffef])', '', cleaned)
    cleaned = re.sub(r'(?<=[\u3000-\u303f\uff00-\uffef])\s+(?=[\u4e00-\u9fff])', '', cleaned)
    return cleaned.strip()


class TreeBuilderService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.settings = get_settings()

        _provider_config = {
            "openrouter": (
                "OPENROUTER_API_KEY",
                "https://openrouter.ai/api/v1",
            ),
            "aliyun": (
                "ALIYUN_API_KEY",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            "deepseek": (
                "DEEPSEEK_API_KEY",
                "https://api.deepseek.com/v1",
            ),
            "openai": (
                "OPENAI_API_KEY",
                "https://api.openai.com/v1",
            ),
            "gemini": (
                "GEMINI_API_KEY",
                "https://generativelanguage.googleapis.com/v1beta/openai/",
            ),
            "minimax": (
                "MINIMAX_API_KEY",
                "https://api.minimaxi.com/anthropic",
            ),
        }

        primary_provider = (self.settings.LLM_HEAVY_MODEL or "aliyun").lower().strip()
        provider_key_attr, provider_base_url = _provider_config.get(
            primary_provider, ("ALIYUN_API_KEY", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        )
        api_key = getattr(self.settings, provider_key_attr, None)
        if api_key:
            os.environ["CHATGPT_API_KEY"] = api_key
            os.environ["CHATGPT_BASE_URL"] = provider_base_url
            if primary_provider == "minimax":
                os.environ["ANTHROPIC_API_KEY"] = api_key
                os.environ["ANTHROPIC_BASE_URL"] = "https://api.minimaxi.com/anthropic"

        # Cache directory for OCR results
        self.cache_dir = Path("cache/page_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def _download_pdf(self, pdf_url: str) -> str:
        """Downloads a PDF from a URL to a local temporary file."""
        os.makedirs("/tmp/treeedu", exist_ok=True)
        pdf_path = os.path.join("/tmp/treeedu", os.path.basename(pdf_url))

        # Async wrapper roughly
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, requests.get, pdf_url)

        if response.status_code == 200:
            with open(pdf_path, "wb") as f:
                f.write(response.content)
            return pdf_path
        else:
            raise Exception(
                f"Failed to download PDF. Status code: {response.status_code}"
            )

    def _get_page_cache_path(self, material_id: str) -> Path:
        """Get OCR cache file path for a material."""
        return self.cache_dir / f"{material_id}_ocr_pages.json"

    def _get_tree_cache_path(self, material_id: str) -> Path:
        """Get tree cache file path for a material."""
        return self.cache_dir / f"{material_id}_tree_structure.json"

    def _get_toc_cache_path(self, material_id: str) -> Path:
        """Get TOC cache file path for a material."""
        return self.cache_dir / f"{material_id}_toc_cache.json"

    def _save_page_cache(
        self, material_id: str, page_num: int, text: str, tokens: int
    ) -> None:
        """Save single page OCR result to cache (sync version)."""
        cache_dir = self.cache_dir / f"{material_id}_pages_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"page_{page_num:04d}.json"

        cache_data = {
            "page_num": page_num,
            "text": text,
            "tokens": tokens,
            "timestamp": datetime.now().isoformat(),
        }
        cache_file.write_text(
            json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[Cache] Saved page {page_num} cache")

    async def _load_page_cache(
        self, material_id: str
    ) -> Optional[List[Tuple[str, int]]]:
        """Load all page cache files for a material."""
        cache_dir = self.cache_dir / f"{material_id}_pages_cache/"

        if not cache_dir.exists():
            return None

        page_list = []
        try:
            cache_files = sorted(
                cache_dir.glob("*.json"), key=lambda x: int(x.stem.split("_")[1])
            )

            for cache_file in cache_files:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    page_list.append((cache_data["text"], cache_data["tokens"]))

            print(f"[Cache] ✅ Loaded {len(page_list)} pages from cache")
            return page_list

        except Exception as e:
            print(f"[Cache] Failed to load cache: {e}")
            return None

    async def clear_material_cache(self, material_id: str) -> None:
        """Clear all cache files for a material."""
        cache_dir = self.cache_dir / f"{material_id}_pages_cache/"

        if not cache_dir.exists():
            return None

        files_deleted = 0
        for cache_file in cache_dir.glob("*.json"):
            cache_file.unlink()
            files_deleted += 1

        print(f"[Cache] Deleted {files_deleted} cache files for material {material_id}")

    async def ingest_material(
        self, material_id: str, pdf_url_or_path: str
    ) -> Dict[str, Any]:
        """
        Main pipeline with unified text caching:
        1. Use PdfTextExtractor to extract text from PDF and cache as txt files
        2. Pass cached page_list to PageIndex (skip internal PDF extraction)
        3. Extract catalog from cached page_list (rule-based first, LLM fallback)
        4. Dual-tree mapping and save KnowledgeNodes to DB
        """
        # Fix Windows GBK encoding issue with Unicode characters in PDF text
        import sys as _sys
        if _sys.platform == 'win32':
            try:
                _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
                _sys.stderr.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass

        # 1. Verify material exists
        result = await self.db.execute(
            select(Material).where(Material.id == material_id)
        )
        material = result.scalars().first()

        if not material:
            raise ValueError(f"Material with id {material_id} not found.")

        # 2. Get local PDF path
        if pdf_url_or_path.startswith("http"):
            local_pdf_path = await self._download_pdf(pdf_url_or_path)
            is_temp = True
        else:
            local_pdf_path = pdf_url_or_path
            is_temp = False

        if not os.path.exists(local_pdf_path):
            raise FileNotFoundError(f"PDF file not found at {local_pdf_path}")

        try:
            # ── STEP 1: 统一文本提取并缓存为 txt ──
            print(f"\n[TEXT-EXTRACT] 开始统一文本提取 for material {material_id}...")
            text_extractor = PdfTextExtractor()
            loop = asyncio.get_event_loop()
            page_list, text_cache_dir = await loop.run_in_executor(
                None,
                lambda: text_extractor.extract_and_cache(local_pdf_path, material_id),
            )
            print(f"[TEXT-EXTRACT] 提取完成: {len(page_list)} 页, 缓存到 {text_cache_dir}")

            # ── STEP 2: PageIndex 树构建（传入 page_list，跳过内部 PDF 提取）──
            import uuid
            from pageindex.utils import ConfigLoader
            from pageindex.page_index import page_index_main

            config_loader = ConfigLoader()
            opt = config_loader.load()

            toc_cache_path = str(self._get_toc_cache_path(material_id))

            # 传入 page_list，PageIndex 不再重新提取
            tree_result = await loop.run_in_executor(
                None,
                lambda: page_index_main(
                    local_pdf_path,
                    opt,
                    progress_callback=None,
                    use_cache=True,
                    page_list=page_list,  # 传入缓存的 page_list
                    start_page=1,
                    cached_pages=None,
                    toc_cache_path=toc_cache_path,
                ),
            )
            doc_id = f"local_{uuid.uuid4()}"

            # 5. Extract structure
            structure = (
                tree_result.get("structure", [])
                if isinstance(tree_result, dict)
                else tree_result
            )

            print(f"[DEBUG] tree_builder received structure type: {type(structure)}")
            if isinstance(structure, list) and len(structure) > 0:
                print(f"[DEBUG] tree_builder structure is list with {len(structure)} items")
                first_item = structure[0]
                if isinstance(first_item, dict):
                    print(f"[DEBUG] First item keys: {first_item.keys()}")
                    if "physical_index" in first_item:
                        print(f"[DEBUG] First item has physical_index: {first_item['physical_index']} (type: {type(first_item['physical_index'])})")
                    if "node_id" in first_item:
                        print(f"[DEBUG] First item has node_id: {first_item['node_id']}")
                    if "structure" in first_item:
                        print(f"[DEBUG] First item has structure field: {first_item['structure']}")
            elif isinstance(structure, dict):
                print(f"[DEBUG] tree_builder structure is dict with keys: {structure.keys()}")

            # ── STEP 3: 目录提取（优先 PageIndex 结果复用，fallback 到规则化/LLM/VLM）──
            from app.utils.vlm_catalog import (
                extract_catalog_from_pdf,
                extract_catalog_from_text,
                extract_catalog_from_page_list,
                map_dual_tree,
                map_dual_tree_rule_based,
            )

            toc_text = tree_result.get("toc_text") if isinstance(tree_result, dict) else None

            catalog_tree = []

            # 3-0. 优先: 从 PageIndex 结果复用构建 catalog_tree（零 LLM 调用）
            pi_catalog_result = build_catalog_from_pageindex(tree_result, page_list)
            if pi_catalog_result is _NEED_TOC_TEXT_PARSE:
                # structure 节点不足但有 toc_text，只执行 3b
                print("[DUAL-TREE] PageIndex structure 节点不足，使用 toc_text 解析")
                if toc_text:
                    print(f"[DUAL-TREE] 从 toc_text 用 LLM 解析目录 ({len(toc_text)} chars)...")
                    catalog_tree = await extract_catalog_from_text(toc_text)
                    print(f"[DUAL-TREE] LLM 文本解析返回 {len(catalog_tree)} 根节点")
            elif pi_catalog_result:
                catalog_tree = pi_catalog_result
                print(f"[DUAL-TREE] 从PageIndex结果构建catalog_tree成功: {len(catalog_tree)} 根节点")
            else:
                # PageIndex 复用失败，继续原有 fallback 逻辑
                # 3a. 优先: 从缓存的 page_list 规则化解析
                if not catalog_tree and page_list:
                    print(f"[DUAL-TREE] 尝试从缓存 page_list 规则化解析目录...")
                    catalog_tree = extract_catalog_from_page_list(page_list)
                    if catalog_tree:
                        print(f"[DUAL-TREE] 规则化解析成功: {len(catalog_tree)} 根节点")

                # 3b. Fallback 1: 从 toc_text 用 LLM 解析
                if not catalog_tree and toc_text:
                    print(f"[DUAL-TREE] Fallback: 从 toc_text 用 LLM 解析目录 ({len(toc_text)} chars)...")
                    catalog_tree = await extract_catalog_from_text(toc_text)
                    print(f"[DUAL-TREE] LLM 文本解析返回 {len(catalog_tree)} 根节点")

                # 3c. Fallback 2: VLM 图片提取（传入 page_list 优先规则化）
                if not catalog_tree:
                    print("[DUAL-TREE] Fallback: VLM 目录提取...")
                    catalog_tree = await extract_catalog_from_pdf(
                        local_pdf_path, page_list=page_list
                    )
                    print(f"[DUAL-TREE] VLM 目录提取返回 {len(catalog_tree)} 根节点")

            # ── STEP 3.5: 双树映射（优先规则化，fallback 到 LLM）──
            mapped_tree = []
            use_catalog_tree = False

            if catalog_tree and len(catalog_tree) > 0:
                # 优先尝试规则化映射
                rule_mapped, rule_coverage = map_dual_tree_rule_based(
                    catalog_tree, structure
                )
                if rule_coverage >= 0.8:
                    mapped_tree = rule_mapped
                    use_catalog_tree = True
                    print(f"[DUAL-TREE] 规则化映射成功，覆盖率: {rule_coverage:.0%}")
                else:
                    # 规则化覆盖率不足，fallback 到 LLM
                    print(f"[DUAL-TREE] 规则化映射覆盖率不足 ({rule_coverage:.0%})，fallback到LLM")
                    mapped_tree = await map_dual_tree(catalog_tree, structure)
                    if mapped_tree:
                        use_catalog_tree = True

            # ── STEP 4: 保存到数据库 ──
            if use_catalog_tree:
                pi_map = {}
                self._flatten_pi_structure(structure, pi_map)
                # Sort top-level nodes by page number to ensure correct unit order
                mapped_tree.sort(key=lambda n: n.get("page") or 0)
                for i, root_node in enumerate(mapped_tree, 1):
                    await self._parse_and_save_vlm_tree(
                        material_id,
                        root_node,
                        pi_map,
                        parent_db_id=None,
                        level=1,
                        seq=i,
                    )
            else:
                # Fallback to the raw PageIndex tree
                if isinstance(structure, list):
                    # Sort top-level nodes by physical_index to ensure correct order
                    structure.sort(key=lambda n: n.get("physical_index") or n.get("start_index") or 0)
                    for i, root_node in enumerate(structure, 1):
                        await self._parse_and_save_tree(
                            material_id, root_node, parent_db_id=None, level=1, seq=i
                        )
                elif isinstance(structure, dict):
                    await self._parse_and_save_tree(
                        material_id, structure, parent_db_id=None, level=1, seq=1
                    )

            # Commit the transaction
            await self.db.commit()

            from app.agent.tools.pageindex_tools import invalidate_candidate_cache
            invalidate_candidate_cache(material_id)

            # Count nodes for reporting
            node_count_result = await self.db.execute(
                select(func.count(KnowledgeNode.id)).where(
                    KnowledgeNode.material_id == material_id
                )
            )
            node_count = node_count_result.scalar() or 0

            return {
                "status": "success",
                "message": f"Successfully built knowledge tree for material {material_id}.",
                "doc_id": doc_id,
                "node_count": node_count,
            }

        finally:
            if is_temp and os.path.exists(local_pdf_path):
                try:
                    os.remove(local_pdf_path)
                except Exception:
                    pass

    def _flatten_pi_structure(
        self, structure: Any, result_map: Dict[str, Dict[str, Any]]
    ) -> None:
        """Helper to flatten PageIndex structure into a lookup map by node_id, preserving all metadata including text."""
        if isinstance(structure, list):
            for item in structure:
                self._flatten_pi_structure(item, result_map)
        elif isinstance(structure, dict):
            node_id = structure.get("node_id")
            if node_id:
                result_map[node_id] = structure

            children = structure.get("nodes", structure.get("children", []))
            for child in children:
                self._flatten_pi_structure(child, result_map)

    async def _parse_and_save_tree(
        self,
        material_id: str,
        node_data: Dict[str, Any],
        parent_db_id: Optional[str] = None,
        level: int = 1,
        seq: int = 1,
    ) -> None:
        """
        Recursively parses the PageIndex JSON tree and saves ORM entities.
        """
        from app.models.material import KnowledgeContent

        # Extract features
        pi_node_id = node_data.get("node_id")
        title = _clean_title(node_data.get("title", f"Node {pi_node_id}"))
        summary = node_data.get("summary", "")
        text_content = node_data.get("text", "")

        # Build structure-only payload for the JSON field
        pi_index_node = {
            k: v for k, v in node_data.items() if k not in ("text", "children", "nodes")
        }

        # Create ORM object for the structural node
        new_node = KnowledgeNode(
            material_id=material_id,
            parent_id=parent_db_id,
            title=title,
            level=level,
            seq_num=seq,
            pageindex_ref=pi_node_id,
            mapped_pi_nodes=[pi_node_id] if pi_node_id else None,
            pi_nodes_json=[pi_index_node] if pi_node_id else None,
        )

        # Add to session
        self.db.add(new_node)
        await self.db.flush()  # Flush to get the generated local ID (uuid)

        # Add KnowledgeContent if text exists
        content_body = (
            f"**Summary:** {summary}\n\n{text_content}" if text_content else summary
        )
        if content_body.strip() and pi_node_id:
            new_content = KnowledgeContent(
                knowledge_node_id=new_node.id,
                pi_node_id=pi_node_id,
                content_md=content_body.strip(),
            )
            self.db.add(new_content)

        # Recursively process children (sorted by physical_index / start_index)
        children = node_data.get("nodes", node_data.get("children", []))
        children.sort(key=lambda c: c.get("physical_index") or c.get("start_index") or 0)
        for i, child in enumerate(children, 1):
            await self._parse_and_save_tree(
                material_id=material_id,
                node_data=child,
                parent_db_id=str(new_node.id),
                level=level + 1,
                seq=i,
            )

    async def _parse_and_save_vlm_tree(
        self,
        material_id: str,
        node_data: Dict[str, Any],
        pi_map: Dict[str, Dict[str, Any]],
        parent_db_id: Optional[str] = None,
        level: int = 1,
        seq: int = 1,
    ) -> None:
        """
        Recursively parses the VLM-generated JSON tree and saves ORM entities.
        """
        from app.models.material import KnowledgeContent

        title = _clean_title(node_data.get("title", f"Node L{level}-{seq}"))
        mapped_nodes = node_data.get("mapped_pi_nodes", [])
        page = node_data.get("page")

        pi_nodes_list = []
        for pi_id in mapped_nodes:
            if pi_id in pi_map:
                pi_data = pi_map[pi_id]
                pi_index_node = {
                    k: v for k, v in pi_data.items() if k not in ("children", "nodes")
                }
                pi_nodes_list.append(pi_index_node)

        # Create ORM object for structural node
        new_node = KnowledgeNode(
            material_id=material_id,
            parent_id=parent_db_id,
            title=title,
            level=level,
            seq_num=seq,
            pageindex_ref=None,  # Only raw trees have this directly mapped 1-to-1
            mapped_pi_nodes=mapped_nodes,
            pi_nodes_json=pi_nodes_list if pi_nodes_list else None,
        )

        # Add to session
        self.db.add(new_node)
        await self.db.flush()  # Flush to get the generated local ID (uuid)

        # Create and link actual Content objects
        for pi_id in mapped_nodes:
            if pi_id in pi_map:
                pi_data = pi_map[pi_id]
                text_content = pi_data.get("text", "")
                summary = pi_data.get("summary", "")

                content_parts = []
                if page:
                    content_parts.append(f"**Source Page:** {page}")

                content_body = (
                    f"**Summary:** {summary}\n\n{text_content}"
                    if text_content
                    else summary
                )
                if content_body.strip():
                    content_parts.append(content_body.strip())

                final_md = "\n\n".join(content_parts)
                if final_md.strip():
                    new_content = KnowledgeContent(
                        knowledge_node_id=new_node.id,
                        pi_node_id=pi_id,
                        content_md=final_md.strip(),
                    )
                    self.db.add(new_content)

        # Recursively process children (sorted by page number)
        children = node_data.get("children", [])
        children.sort(key=lambda c: c.get("page") or 0)
        for i, child in enumerate(children, 1):
            await self._parse_and_save_vlm_tree(
                material_id=material_id,
                node_data=child,
                pi_map=pi_map,
                parent_db_id=str(new_node.id),
                level=level + 1,
                seq=i,
            )
