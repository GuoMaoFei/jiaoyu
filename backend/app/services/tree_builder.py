import os
import requests
import asyncio
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.models.material import Material, KnowledgeNode

class TreeBuilderService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.settings = get_settings()
        
        # Set Aliyun key and base url for PageIndex local usage
        if self.settings.ALIYUN_API_KEY:
            os.environ["CHATGPT_API_KEY"] = self.settings.ALIYUN_API_KEY
            os.environ["CHATGPT_BASE_URL"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"


    async def _download_pdf(self, pdf_url: str) -> str:
        """Downloads a PDF from a URL to a local temporary file."""
        os.makedirs("/tmp/treeedu", exist_ok=True)
        pdf_path = os.path.join("/tmp/treeedu", os.path.basename(pdf_url))
        
        # Async wrapper roughly
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, requests.get, pdf_url)
        
        if response.status_code == 200:
            with open(pdf_path, 'wb') as f:
                f.write(response.content)
            return pdf_path
        else:
            raise Exception(f"Failed to download PDF. Status code: {response.status_code}")

    async def ingest_material(self, material_id: str, pdf_url_or_path: str) -> Dict[str, Any]:
        """
        Main pipeline:
        1. Query material from DB.
        2. Upload PDF to PageIndex to get doc_id.
        3. Wait for tree generation.
        4. Parse JSON tree and save as KNOWLEDGE_NODEs to DB mapping to material_id.
        """
        # 1. Verify material exists
        result = await self.db.execute(select(Material).where(Material.id == material_id))
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
            # 3. Process with Local PageIndex
            import uuid
            from pageindex.utils import ConfigLoader
            from pageindex.page_index import page_index_main
            
            config_loader = ConfigLoader()
            user_opt = {
                'model': 'qwen-max', # Use Aliyun's flagship model instead of gpt-4o
                'if_add_node_summary': 'yes',
                'if_add_doc_description': 'no',
                'if_add_node_text': 'yes', # needed for node matching later
                'if_add_node_id': 'yes'
            }
            opt = config_loader.load(user_opt)
            
            loop = asyncio.get_event_loop()
            # Local PageIndex does synchronous blocking work internally
            tree_result = await loop.run_in_executor(
                None, 
                lambda: page_index_main(local_pdf_path, opt)
            )
            doc_id = f"local_{uuid.uuid4()}"

            # 5. Extract structure
            structure = tree_result.get("structure", []) if isinstance(tree_result, dict) else tree_result
            
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
                    await self._parse_and_save_vlm_tree(material_id, root_node, pi_map, parent_db_id=None, level=1, seq=i)
            else:
                # Fallback to the raw PageIndex tree
                if isinstance(structure, list):
                    for i, root_node in enumerate(structure, 1):
                        await self._parse_and_save_tree(material_id, root_node, parent_db_id=None, level=1, seq=i)
                elif isinstance(structure, dict):
                    await self._parse_and_save_tree(material_id, structure, parent_db_id=None, level=1, seq=1)
            
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

    def _flatten_pi_structure(self, structure: Any, result_map: Dict[str, Dict[str, Any]]) -> None:
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

    async def _parse_and_save_tree(self, material_id: str, node_data: Dict[str, Any], parent_db_id: Optional[str] = None, level: int = 1, seq: int = 1) -> None:
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
        pi_index_node = {k: v for k, v in node_data.items() if k not in ("text", "children")}
        
        # Create ORM object for the structural node
        new_node = KnowledgeNode(
            material_id=material_id,
            parent_id=parent_db_id,
            title=title,
            level=level,
            seq_num=seq,
            pageindex_ref=pi_node_id,
            mapped_pi_nodes=[pi_node_id] if pi_node_id else None,
            pi_nodes_json=[pi_index_node] if pi_node_id else None
        )
        
        # Add to session
        self.db.add(new_node)
        await self.db.flush() # Flush to get the generated local ID (uuid)
        
        # Add KnowledgeContent if text exists
        content_body = f"**Summary:** {summary}\n\n{text_content}" if text_content else summary
        if content_body.strip() and pi_node_id:
            new_content = KnowledgeContent(
                knowledge_node_id=new_node.id,
                pi_node_id=pi_node_id,
                content_md=content_body.strip()
            )
            self.db.add(new_content)
        
        # Recursively process children
        children = node_data.get("children", [])
        for i, child in enumerate(children, 1):
            await self._parse_and_save_tree(
                material_id=material_id, 
                node_data=child, 
                parent_db_id=new_node.id, 
                level=level + 1, 
                seq=i
            )

    async def _parse_and_save_vlm_tree(self, material_id: str, node_data: Dict[str, Any], pi_map: Dict[str, Dict[str, Any]], parent_db_id: Optional[str] = None, level: int = 1, seq: int = 1) -> None:
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
                pi_index_node = {k: v for k, v in pi_data.items() if k not in ("text", "children")}
                pi_nodes_list.append(pi_index_node)
        
        # Create ORM object for structural node
        new_node = KnowledgeNode(
            material_id=material_id,
            parent_id=parent_db_id,
            title=title,
            level=level,
            seq_num=seq,
            pageindex_ref=None, # Only raw trees have this directly mapped 1-to-1
            mapped_pi_nodes=mapped_nodes,
            pi_nodes_json=pi_nodes_list if pi_nodes_list else None
        )
        
        # Add to session
        self.db.add(new_node)
        await self.db.flush() # Flush to get the generated local ID (uuid)
        
        # Create and link actual Content objects
        for pi_id in mapped_nodes:
            if pi_id in pi_map:
                pi_data = pi_map[pi_id]
                text_content = pi_data.get("text", "")
                summary = pi_data.get("summary", "")
                
                content_parts = []
                if page:
                    content_parts.append(f"**Source Page:** {page}")
                
                content_body = f"**Summary:** {summary}\n\n{text_content}" if text_content else summary
                if content_body.strip():
                    content_parts.append(content_body.strip())
                    
                final_md = "\n\n".join(content_parts)
                if final_md.strip():
                    new_content = KnowledgeContent(
                        knowledge_node_id=new_node.id,
                        pi_node_id=pi_id,
                        content_md=final_md.strip()
                    )
                    self.db.add(new_content)
        
        # Recursively process children
        children = node_data.get("children", [])
        for i, child in enumerate(children, 1):
            await self._parse_and_save_vlm_tree(
                material_id=material_id, 
                node_data=child, 
                pi_map=pi_map,
                parent_db_id=new_node.id, 
                level=level + 1, 
                seq=i
            )


