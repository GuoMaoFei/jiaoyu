"""
Vision OCR Utility - Converts images (photos of homework, handwritten solutions)
to text/LaTeX for processing by the LLM.

Uses the LLM's native vision capability to extract text and mathematical expressions.
"""
import base64
import logging
from typing import Optional
from pathlib import Path

from langchain_core.messages import HumanMessage
from app.utils.llm_router import get_heavy_model

logger = logging.getLogger(__name__)

VISION_PROMPT = """你是一个精准的 OCR 专家。请仔细阅读这张图片，提取其中的全部文字和数学公式。

要求：
1. 数学公式使用 LaTeX 格式，用 $...$ 包裹行内公式，$$...$$ 包裹独立公式
2. 保持原文的段落结构和编号
3. 如果有手写内容，尽可能准确识别
4. 如果图片不清晰或无法识别，请如实说明

请直接输出识别结果，不要添加额外说明。"""


async def extract_text_from_image(image_source: str) -> dict:
    """
    Extract text and LaTeX from an image using the LLM's vision capability.
    
    Args:
        image_source: Either a URL (http/https), a base64 string, or a local file path.
    
    Returns:
        dict with 'status', 'text', and optionally 'error'.
    """
    try:
        # Determine image format for the LLM
        if image_source.startswith(("http://", "https://")):
            image_content = {
                "type": "image_url",
                "image_url": {"url": image_source}
            }
        elif image_source.startswith("data:"):
            # Already a data URL
            image_content = {
                "type": "image_url",
                "image_url": {"url": image_source}
            }
        else:
            # Assume it's a local file path
            path = Path(image_source)
            if not path.exists():
                return {"status": "error", "text": "", "error": f"File not found: {image_source}"}
            
            # Read and convert to base64
            suffix = path.suffix.lower()
            mime_map = {
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".gif": "image/gif",
                ".webp": "image/webp", ".bmp": "image/bmp",
            }
            mime_type = mime_map.get(suffix, "image/jpeg")
            
            with open(path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")
            
            image_content = {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}
            }
        
        # Call the vision-capable LLM
        model = get_heavy_model(temperature=0)
        
        message = HumanMessage(
            content=[
                {"type": "text", "text": VISION_PROMPT},
                image_content,
            ]
        )
        
        response = await model.ainvoke([message])
        
        extracted_text = response.content if hasattr(response, 'content') else str(response)
        
        logger.info(f"OCR extracted {len(extracted_text)} chars from image")
        
        return {
            "status": "ok",
            "text": extracted_text,
        }
        
    except Exception as e:
        logger.exception(f"OCR extraction failed: {e}")
        return {
            "status": "error",
            "text": "",
            "error": str(e),
        }
