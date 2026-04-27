"""
PdfTextExtractor - 统一 PDF 文本提取入口

将 PDF 的文本提取和 OCR 统一为一个入口，
提取结果缓存为逐页 txt 文件，供后续树构建和目录解析统一使用。

流程:
  PDF → 文本提取(PyMuPDF/PyPDF2/EasyOCR/VLM-OCR) → cache/text_cache/{material_id}/page_XXXX.txt
"""

import os
import re
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class PdfTextExtractor:
    """统一 PDF 文本提取器，结果缓存为 txt 文件。"""

    def __init__(self, cache_dir: str = "cache/text_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ── 公开接口 ──────────────────────────────────────────────

    def extract_and_cache(
        self,
        pdf_path: str,
        material_id: str,
        force: bool = False,
    ) -> Tuple[List[Tuple[str, int]], Path]:
        """
        从 PDF 提取文本并缓存为逐页 txt 文件。

        Args:
            pdf_path: PDF 文件路径
            material_id: 教材 ID，用于缓存目录名
            force: 是否强制重新提取（忽略已有缓存）

        Returns:
            (page_list, cache_dir_path)
            page_list: [(page_text, token_count), ...]
            cache_dir_path: 缓存目录路径
        """
        material_cache_dir = self.cache_dir / material_id
        material_cache_dir.mkdir(parents=True, exist_ok=True)

        # 检查已有缓存
        if not force:
            cached = self._load_from_cache(material_cache_dir)
            if cached is not None:
                logger.info(f"[PdfTextExtractor] 已有缓存: {len(cached)} 页, 跳过提取")
                return cached, material_cache_dir

        # 执行提取
        logger.info(f"[PdfTextExtractor] 开始提取: {pdf_path}")
        page_list = self._extract_text(pdf_path)

        # 保存缓存
        self._save_to_cache(material_cache_dir, page_list)
        logger.info(f"[PdfTextExtractor] 提取完成: {len(page_list)} 页, 已缓存到 {material_cache_dir}")

        return page_list, material_cache_dir

    def load_cache(self, material_id: str) -> Optional[List[Tuple[str, int]]]:
        """从缓存加载已提取的文本，不存在则返回 None。"""
        material_cache_dir = self.cache_dir / material_id
        return self._load_from_cache(material_cache_dir)

    def clear_cache(self, material_id: str) -> int:
        """清除指定教材的文本缓存，返回删除的文件数。"""
        material_cache_dir = self.cache_dir / material_id
        if not material_cache_dir.exists():
            return 0
        count = 0
        for f in material_cache_dir.glob("*"):
            f.unlink()
            count += 1
        material_cache_dir.rmdir()
        return count

    # ── 缓存读写 ──────────────────────────────────────────────

    def _load_from_cache(
        self, cache_dir: Path
    ) -> Optional[List[Tuple[str, int]]]:
        """从缓存目录加载 page_XXXX.txt 文件。"""
        txt_files = sorted(cache_dir.glob("page_*.txt"))
        if not txt_files:
            return None

        page_list = []
        for txt_file in txt_files:
            text = txt_file.read_text(encoding="utf-8")
            token_count = self._estimate_tokens(text)
            page_list.append((text, token_count))

        return page_list

    def _save_to_cache(
        self, cache_dir: Path, page_list: List[Tuple[str, int]]
    ) -> None:
        """将 page_list 保存为逐页 txt 文件。"""
        # 同时保存一个 meta.json 记录元信息
        meta = {
            "total_pages": len(page_list),
            "timestamp": datetime.now().isoformat(),
            "pages": [],
        }

        for i, (text, tokens) in enumerate(page_list):
            page_num = i + 1
            txt_file = cache_dir / f"page_{page_num:04d}.txt"
            txt_file.write_text(text, encoding="utf-8")

            meta["pages"].append({
                "page_num": page_num,
                "text_length": len(text),
                "tokens": tokens,
            })

        meta_file = cache_dir / "meta.json"
        meta_file.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── 文本提取核心 ──────────────────────────────────────────

    def _extract_text(self, pdf_path: str) -> List[Tuple[str, int]]:
        """
        从 PDF 提取文本，按优先级尝试多种方法:
        1. PyMuPDF 直提
        2. PyPDF2 直提
        3. EasyOCR (本地 OCR)
        4. VLM OCR (Kimi-2.5, 需 API)
        """
        # 1. PyMuPDF
        page_list = self._try_pymupdf(pdf_path)
        if page_list and not self._needs_ocr(page_list):
            logger.info(f"[PdfTextExtractor] PyMuPDF 提取成功: {len(page_list)} 页")
            return page_list

        # 2. PyPDF2
        page_list = self._try_pypdf2(pdf_path)
        if page_list and not self._needs_ocr(page_list):
            logger.info(f"[PdfTextExtractor] PyPDF2 提取成功: {len(page_list)} 页")
            return page_list

        # 3. EasyOCR
        logger.info("[PdfTextExtractor] 直提文本不足，尝试 EasyOCR...")
        page_list = self._try_easyocr(pdf_path)
        if page_list and not self._needs_ocr(page_list):
            logger.info(f"[PdfTextExtractor] EasyOCR 提取成功: {len(page_list)} 页")
            return page_list

        # 4. VLM OCR (Kimi)
        logger.info("[PdfTextExtractor] EasyOCR 不足，尝试 VLM OCR...")
        page_list = self._try_vlm_ocr(pdf_path)
        if page_list:
            logger.info(f"[PdfTextExtractor] VLM OCR 提取成功: {len(page_list)} 页")
            return page_list

        logger.warning("[PdfTextExtractor] 所有提取方法均失败")
        return []

    def _try_pymupdf(self, pdf_path: str) -> Optional[List[Tuple[str, int]]]:
        """PyMuPDF 直提文本。"""
        try:
            import pymupdf
            doc = pymupdf.open(pdf_path)
            page_list = []
            for page in doc:
                text = page.get_text()
                tokens = self._estimate_tokens(text)
                page_list.append((text, tokens))
            doc.close()
            return page_list
        except Exception as e:
            logger.warning(f"[PdfTextExtractor] PyMuPDF 失败: {e}")
            return None

    def _try_pypdf2(self, pdf_path: str) -> Optional[List[Tuple[str, int]]]:
        """PyPDF2 直提文本。"""
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(pdf_path)
            page_list = []
            for page in reader.pages:
                text = page.extract_text()
                tokens = self._estimate_tokens(text)
                page_list.append((text, tokens))
            return page_list
        except Exception as e:
            logger.warning(f"[PdfTextExtractor] PyPDF2 失败: {e}")
            return None

    def _try_easyocr(self, pdf_path: str) -> Optional[List[Tuple[str, int]]]:
        """EasyOCR 本地 OCR 提取。"""
        try:
            import easyocr
            import pymupdf
            import cv2
            import numpy as np

            reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
            doc = pymupdf.open(pdf_path)
            total_pages = len(doc)
            doc.close()

            page_list = []
            for page_num in range(total_pages):
                doc = pymupdf.open(pdf_path)
                page = doc[page_num]
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
                img_data = pix.tobytes("png")
                doc.close()

                img_array = np.frombuffer(img_data, dtype=np.uint8)
                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                result = reader.readtext(img, detail=0)
                text = "\n".join(result) if result else ""
                tokens = self._estimate_tokens(text)
                page_list.append((text, tokens))

            return page_list
        except ImportError:
            logger.warning("[PdfTextExtractor] EasyOCR 未安装")
            return None
        except Exception as e:
            logger.warning(f"[PdfTextExtractor] EasyOCR 失败: {e}")
            return None

    def _try_vlm_ocr(self, pdf_path: str) -> Optional[List[Tuple[str, int]]]:
        """VLM OCR 提取（Kimi-2.5），逐页调用。"""
        try:
            import pymupdf
            import base64
            import httpx
            import time

            api_key = os.getenv("KIMI_API_KEY") or os.getenv("CHATGPT_API_KEY")
            if not api_key:
                logger.warning("[PdfTextExtractor] 未配置 KIMI_API_KEY，跳过 VLM OCR")
                return None

            base_url = "https://ark.cn-beijing.volces.com/api/coding/v3"
            model = os.getenv("KIMI_OCR_MODEL", "kimi-k2.5")

            doc = pymupdf.open(pdf_path)
            total_pages = len(doc)
            doc.close()

            page_list = []
            for page_num in range(total_pages):
                doc = pymupdf.open(pdf_path)
                page = doc[page_num]
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
                img_data = pix.tobytes("png")
                img_base64 = base64.b64encode(img_data).decode("utf-8")
                doc.close()

                message = {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "你是一个精准的 OCR 专家。请仔细阅读这张图片，提取其中的全部文字。直接输出结果，不要有任何解释。",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                        },
                    ],
                }

                try:
                    client = httpx.Client(timeout=300.0)
                    response = client.post(
                        f"{base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={"model": model, "messages": [message], "temperature": 0, "max_tokens": 8192},
                    )
                    client.close()

                    if response.status_code == 200:
                        result = response.json()
                        text = result["choices"][0]["message"]["content"]
                    else:
                        logger.warning(f"[VLM-OCR] Page {page_num + 1} API error: {response.status_code}")
                        text = ""
                except Exception as e:
                    logger.warning(f"[VLM-OCR] Page {page_num + 1} failed: {e}")
                    text = ""

                tokens = self._estimate_tokens(text)
                page_list.append((text, tokens))

                if page_num < total_pages - 1:
                    time.sleep(0.5)

            return page_list
        except Exception as e:
            logger.warning(f"[PdfTextExtractor] VLM OCR 失败: {e}")
            return None

    # ── 工具方法 ──────────────────────────────────────────────

    @staticmethod
    def _needs_ocr(page_list: List[Tuple[str, int]]) -> bool:
        """判断提取的文本是否不足，需要 OCR。"""
        if not page_list:
            return True
        total_text = sum(len(p[0]) for p in page_list)
        avg_text = total_text / len(page_list)
        return avg_text < 100

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """估算 token 数（中文约 1.5 字/token，英文约 4 字/token）。"""
        if not text:
            return 0
        # 简单估算: 中文字符数 / 1.5 + 英文单词数
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)

    @staticmethod
    def get_toc_pages_text(page_list: List[Tuple[str, int]], toc_page_indices: List[int]) -> str:
        """
        从 page_list 中提取指定目录页的文本，拼接为一段。

        Args:
            page_list: [(text, tokens), ...]
            toc_page_indices: 目录页索引列表（0-based）

        Returns:
            拼接的目录文本
        """
        toc_texts = []
        for idx in toc_page_indices:
            if 0 <= idx < len(page_list):
                toc_texts.append(page_list[idx][0])
        return "\n\n".join(toc_texts)

    @staticmethod
    def detect_toc_pages(page_list: List[Tuple[str, int]]) -> List[int]:
        """
        规则化检测目录页：搜索包含"目录"/"目次"/"Contents"等关键词的页面。

        Args:
            page_list: [(text, tokens), ...]

        Returns:
            目录页索引列表（0-based）
        """
        toc_keywords = ["目录", "目  录", "目次", "CONTENTS", "Contents", "contents", "Table of Contents"]
        toc_pages = []

        for i, (text, _) in enumerate(page_list):
            # 只在前 20 页搜索目录页
            if i >= 20:
                break
            for kw in toc_keywords:
                if kw in text:
                    # 排除正文中偶然出现"目录"的情况：目录页通常文本较短
                    # 且包含多个章节条目（缩进+点号+页码的模式）
                    has_toc_pattern = bool(
                        re.search(r'第[一二三四五六七八九十]+[章节单元]', text)
                        or re.search(r'\.{3,}\s*\d+', text)  # "...... 12" 模式
                        or re.search(r'\d+\.\d+', text)       # "1.1" 编号模式
                    )
                    if has_toc_pattern or len(text) < 2000:
                        toc_pages.append(i)
                    break

        return toc_pages
