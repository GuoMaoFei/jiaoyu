"""数据模型定义 - kp_pdf_test 模块的所有 dataclass"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class Chapter:
    """教材章节"""
    title: str            # 章节标题，如"第一单元：准备课"
    content: List[str]    # 正文行列表
    level: int = 1        # 标题层级：1=章，2=节


@dataclass
class PDFGenConfig:
    """PDF 生成配置"""
    title: str                          # PDF 标题
    author: str = "KP-PDF-Test"        # 作者
    chapters: List[Chapter] = field(default_factory=list)  # 章节列表
    output_path: str = "test_output.pdf"  # 输出路径
    subject: str = "数学"               # 学科
    grade: str = "一年级"               # 年级


@dataclass
class PageResult:
    """单页解析结果"""
    page_num: int    # 页码，从1开始
    text: str        # 提取的文本内容
    tokens: int      # token 数量


@dataclass
class ParseResult:
    """PDF 解析结果"""
    pages: List[PageResult]    # 各页解析结果
    strategy: str              # 解析策略名称
    total_tokens: int          # 总 token 数
    total_chars: int           # 总字符数
    pdf_path: str              # 源 PDF 路径


@dataclass
class ExtractedKnowledgePoint:
    """提取的知识点（测试用，不依赖数据库）"""
    title: str                # 知识点名称
    summary: str              # 一句话概括
    keywords: str             # 逗号分隔的关键词
    level: int                # 深度层级 1-4
    parent_title: str         # 上级主题名称
    relevance: int            # 核心程度 0-100
    source_chapter: str       # 来源章节标题


@dataclass
class E2EResult:
    """端到端测试结果"""
    pdf_path: str                              # 生成的 PDF 路径
    parse_result: Optional[ParseResult] = None # 解析结果
    knowledge_points: List[ExtractedKnowledgePoint] = field(default_factory=list)
    stage_results: dict = field(default_factory=dict)  # 各阶段执行状态
    total_duration: float = 0.0                # 总耗时（秒）
