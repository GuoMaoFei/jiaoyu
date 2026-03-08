"""
Vision OCR Utility - Converts images (photos of homework, handwritten solutions)
to text/LaTeX for processing by the LLM.

Uses the LLM's native vision capability to extract text and mathematical expressions.
"""

import base64
import ipaddress
import logging
import re
from typing import Optional
from pathlib import Path
from urllib.parse import urlparse

from langchain_core.messages import HumanMessage
from app.utils.llm_router import get_vision_model

logger = logging.getLogger(__name__)

VISION_PROMPT = """你是一个精准的 OCR 专家。请仔细阅读这张图片，提取其中的全部文字和数学公式。

要求：
1. 数学公式使用 LaTeX 格式，用 $...$ 包裹行内公式，$$...$$ 包裹独立公式
2. 保持原文的段落结构和编号
3. 如果有手写内容，尽可能准确识别
4. 如果图片不清晰或无法识别，请如实说明

请直接输出识别结果，不要添加额外说明。"""

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
]


def is_safe_url(url: str) -> bool:
    """Validate URL to prevent SSRF attacks."""
    try:
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        if hostname in ("localhost", "local", "0.0.0.0"):
            return False

        try:
            ip = ipaddress.ip_address(hostname)
            for blocked_range in BLOCKED_IP_RANGES:
                if ip in blocked_range:
                    return False
        except ValueError:
            pass

        if re.match(r"^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)", hostname):
            return False

        return True
    except Exception:
        return False


def validate_image_source(image_source: str) -> tuple[bool, str]:
    """
    Validate image source for security.
    Returns (is_valid, error_message).
    """
    if not image_source or len(image_source) > 2048:
        return False, "Invalid image source"

    if image_source.startswith("data:"):
        if not image_source.startswith("data:image/"):
            return False, "Invalid data URL format"
        return True, ""

    if image_source.startswith(("http://", "https://")):
        if not is_safe_url(image_source):
            return False, "URL not allowed for security reasons"
        return True, ""

    return False, "Only base64 data URLs and public HTTP/HTTPS URLs are allowed"


async def extract_text_from_image(image_source: str) -> dict:
    """
    Extract text and LaTeX from an image using the LLM's vision capability.

    Args:
        image_source: Either a public URL (http/https) or a base64 data URL.

    Returns:
        dict with 'status', 'text', and optionally 'error'.
    """
    try:
        is_valid, error_msg = validate_image_source(image_source)
        if not is_valid:
            return {"status": "error", "text": "", "error": error_msg}

        if image_source.startswith(("http://", "https://")):
            image_content = {"type": "image_url", "image_url": {"url": image_source}}
        elif image_source.startswith("data:"):
            image_content = {"type": "image_url", "image_url": {"url": image_source}}
        else:
            return {"status": "error", "text": "", "error": "Unsupported image source"}

        model = get_vision_model(temperature=0)

        message = HumanMessage(
            content=[
                {"type": "text", "text": VISION_PROMPT},
                image_content,
            ]
        )

        response = await model.ainvoke([message])

        extracted_text = (
            response.content if hasattr(response, "content") else str(response)
        )

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
            "error": "OCR processing failed",
        }
