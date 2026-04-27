"""解析策略管理器 - 策略模式实现PDF解析，支持多策略注册和对比"""

import logging
import os
from abc import ABC, abstractmethod

import tiktoken

from .models import PageResult

logger = logging.getLogger(__name__)

# tiktoken encoding 缓存
_encoding = None


def _get_encoding():
    """获取tiktoken encoding实例（缓存）"""
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.get_encoding("cl100k_base")
    return _encoding


def _count_tokens(text: str) -> int:
    """计算文本的token数量"""
    if not text:
        return 0
    return len(_get_encoding().encode(text))


class ParseStrategy(ABC):
    """解析策略抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称"""
        ...

    @abstractmethod
    def extract(self, pdf_path: str, max_pages: int | None = None) -> list[PageResult]:
        """从PDF提取文本

        Args:
            pdf_path: PDF文件路径
            max_pages: 最大解析页数，None表示全部

        Returns:
            各页解析结果列表
        """
        ...


class PyPDF2Strategy(ParseStrategy):
    """PyPDF2解析策略"""

    @property
    def name(self) -> str:
        return "pypdf2"

    def extract(self, pdf_path: str, max_pages: int | None = None) -> list[PageResult]:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        import PyPDF2

        results = []
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            total_pages = len(reader.pages)
            end_page = min(total_pages, max_pages) if max_pages else total_pages

            for i in range(end_page):
                text = reader.pages[i].extract_text() or ""
                tokens = _count_tokens(text)
                results.append(PageResult(page_num=i + 1, text=text, tokens=tokens))

        return results


class PyMuPDFStrategy(ParseStrategy):
    """PyMuPDF解析策略"""

    @property
    def name(self) -> str:
        return "pymupdf"

    def extract(self, pdf_path: str, max_pages: int | None = None) -> list[PageResult]:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        import pymupdf

        results = []
        doc = pymupdf.open(pdf_path)
        try:
            total_pages = doc.page_count
            end_page = min(total_pages, max_pages) if max_pages else total_pages

            for i in range(end_page):
                page = doc[i]
                text = page.get_text() or ""
                tokens = _count_tokens(text)
                results.append(PageResult(page_num=i + 1, text=text, tokens=tokens))
        finally:
            doc.close()

        return results


class StrategyManager:
    """策略管理器 - 管理解析策略的注册和调度"""

    def __init__(self) -> None:
        self._strategies: dict[str, ParseStrategy] = {}

    def register(self, strategy: ParseStrategy) -> None:
        """注册策略"""
        self._strategies[strategy.name] = strategy
        logger.info(f"已注册解析策略: {strategy.name}")

    def get(self, name: str) -> ParseStrategy:
        """获取策略

        Raises:
            KeyError: 策略不存在时
        """
        if name not in self._strategies:
            available = ", ".join(self._strategies.keys())
            raise KeyError(f"解析策略 '{name}' 不存在，可用策略: {available}")
        return self._strategies[name]

    def list_strategies(self) -> list[str]:
        """列出所有已注册策略名称"""
        return list(self._strategies.keys())

    def compare(self, pdf_path: str, strategy_names: list[str] | None = None) -> dict:
        """对比多个策略的解析结果

        Args:
            pdf_path: PDF文件路径
            strategy_names: 要对比的策略名称列表，None表示全部

        Returns:
            对比报告字典 {strategy_name: {total_chars, total_tokens, page_lengths}}
        """
        if strategy_names is None:
            strategy_names = self.list_strategies()

        report = {}
        for name in strategy_names:
            strategy = self.get(name)
            pages = strategy.extract(pdf_path)
            report[name] = {
                "total_chars": sum(len(p.text) for p in pages),
                "total_tokens": sum(p.tokens for p in pages),
                "page_lengths": [len(p.text) for p in pages],
            }

        return report
