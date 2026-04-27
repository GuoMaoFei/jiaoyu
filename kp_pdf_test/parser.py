"""PDF解析器 - 整合策略管理器，提供解析、对比、信息读取、JSON输出等高层接口"""

import json
import logging
import os
from dataclasses import asdict

import PyPDF2

from .models import ParseResult
from .strategy_manager import PyPDF2Strategy, PyMuPDFStrategy, StrategyManager

logger = logging.getLogger(__name__)


class PDFParser:
    """PDF解析器，整合策略管理器提供高层接口"""

    def __init__(self) -> None:
        self.manager = StrategyManager()
        self.manager.register(PyPDF2Strategy())
        self.manager.register(PyMuPDFStrategy())

    def parse(self, pdf_path: str, strategy: str = "pymupdf") -> ParseResult:
        """使用指定策略解析PDF

        Args:
            pdf_path: PDF文件路径
            strategy: 解析策略名称

        Returns:
            ParseResult 解析结果

        Raises:
            FileNotFoundError: PDF文件不存在时
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        parse_strategy = self.manager.get(strategy)
        pages = parse_strategy.extract(pdf_path)
        total_tokens = sum(p.tokens for p in pages)
        total_chars = sum(len(p.text) for p in pages)

        return ParseResult(
            pages=pages,
            strategy=strategy,
            total_tokens=total_tokens,
            total_chars=total_chars,
            pdf_path=pdf_path,
        )

    def parse_all(self, pdf_path: str) -> dict[str, ParseResult]:
        """使用所有已注册策略解析PDF

        Returns:
            {strategy_name: ParseResult} 字典
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        results = {}
        for name in self.manager.list_strategies():
            results[name] = self.parse(pdf_path, name)
        return results

    def compare_strategies(self, pdf_path: str) -> dict:
        """对比所有策略的解析结果"""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
        return self.manager.compare(pdf_path)

    def get_info(self, pdf_path: str) -> dict:
        """获取PDF基本信息

        Returns:
            包含 total_pages, title, file_size 的字典
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            total_pages = len(reader.pages)
            title = reader.metadata.title if reader.metadata else None

        file_size = os.path.getsize(pdf_path)

        return {
            "total_pages": total_pages,
            "title": title,
            "file_size": file_size,
        }

    def save_result(self, result: ParseResult, output_path: str) -> None:
        """将解析结果保存为JSON文件"""
        data = asdict(result)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"解析结果已保存: {output_path}")
