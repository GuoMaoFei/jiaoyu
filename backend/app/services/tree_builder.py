import os
import json
import requests
import asyncio
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.models.material import Material, KnowledgeNode


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
        Main pipeline with caching:
        1. Check OCR cache first (saves ~36 minutes)
        2. Query material from DB.
        3. Upload PDF to PageIndex or use cached data
        4. Wait for tree generation.
        5. Parse JSON tree and save as KNOWLEDGE_NODEs to DB mapping to material_id.
        6. Save tree cache.
        """
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

        # --- CACHE CHECK (STEP 1) ---
        print(f"\n[CACHE] Checking OCR cache for material {material_id}...")

        page_list = None

        # Try to load OCR cache
        cached_pages = await self._load_page_cache(material_id)
        if cached_pages:
            print(
                f"[CACHE] ✅ Found {len(cached_pages)} cached pages, will resume from next page"
            )
        else:
            cached_pages = []
            print(f"[CACHE] No OCR cache found, running EasyOCR from page 1...")

        try:
            # 3. Process with Local PageIndex (skip if cache exists)
            import uuid
            from pageindex.utils import ConfigLoader
            from pageindex.page_index import page_index_main

            config_loader = ConfigLoader()
            opt = config_loader.load()

            loop = asyncio.get_event_loop()

            # Get PDF total pages for resume logic
            import pymupdf

            pdf_doc = pymupdf.open(local_pdf_path)
            total_pdf_pages = len(pdf_doc)
            pdf_doc.close()

            # Calculate start page for resume
            # When cached_count >= total_pdf_pages, all pages are cached and start_page > cached_count
            # will trigger early return in get_page_tokens
            cached_count = len(cached_pages) if cached_pages else 0
            start_page = cached_count + 1 if cached_count < total_pdf_pages else total_pdf_pages + 1

            # Create progress callback for per-page caching (sync version)
            # Only create callback if we need to OCR more pages
            progress_callback = None
            if cached_count < total_pdf_pages:

                def progress_callback(page_num, text, tokens):
                    self._save_page_cache(material_id, page_num, text, tokens)

            # Local PageIndex does synchronous blocking work internally
            # Note: use_cache=True is needed so that cached_pages is actually used in get_page_tokens
            toc_cache_path = str(self._get_toc_cache_path(material_id))
            tree_result = await loop.run_in_executor(
                None,
                lambda: page_index_main(
                    local_pdf_path,
                    opt,
                    progress_callback=progress_callback,
                    use_cache=True,
                    page_list=None,
                    start_page=start_page,
                    cached_pages=cached_pages,
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

            # --- DUAL-TREE MAPPING INTEGRATION ---
            from app.utils.vlm_catalog import extract_catalog_from_pdf, map_dual_tree

            # Opt 1: Extract real catalog via VLM
            vlm_tree = await extract_catalog_from_pdf(local_pdf_path)

            mapped_tree = []
            use_vlm_tree = False

            if vlm_tree and len(vlm_tree) > 0:
                # Opt 2: Map the raw tree to the VLM Tree
                mapped_tree = await map_dual_tree(vlm_tree, structure)
                if mapped_tree:
                    use_vlm_tree = True

            # 6. Parse and Save to Database
            if use_vlm_tree:
                pi_map = {}
                self._flatten_pi_structure(structure, pi_map)
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

            return {
                "status": "success",
                "message": f"Successfully built knowledge tree for material {material_id}.",
                "doc_id": doc_id,
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

            for child in structure.get("children", []):
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
        title = node_data.get("title", f"Node {pi_node_id}")
        summary = node_data.get("summary", "")
        text_content = node_data.get("text", "")

        # Build structure-only payload for the JSON field
        pi_index_node = {
            k: v for k, v in node_data.items() if k not in ("text", "children")
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

        # Recursively process children
        children = node_data.get("children", [])
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

        title = node_data.get("title", f"Node L{level}-{seq}")
        mapped_nodes = node_data.get("mapped_pi_nodes", [])
        page = node_data.get("page")

        pi_nodes_list = []
        for pi_id in mapped_nodes:
            if pi_id in pi_map:
                pi_data = pi_map[pi_id]
                pi_index_node = {
                    k: v for k, v in pi_data.items() if k not in ("children")
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

        # Recursively process children
        children = node_data.get("children", [])
        for i, child in enumerate(children, 1):
            await self._parse_and_save_vlm_tree(
                material_id=material_id,
                node_data=child,
                pi_map=pi_map,
                parent_db_id=str(new_node.id),
                level=level + 1,
                seq=i,
            )
