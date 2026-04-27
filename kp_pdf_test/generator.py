"""PDF生成器 - 使用reportlab生成包含中文内容的测试PDF文件"""

import logging
import os

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .models import PDFGenConfig, Chapter

logger = logging.getLogger(__name__)


class PDFGenerator:
    """PDF生成器，使用reportlab Canvas绘制包含中文的测试PDF"""

    def __init__(self, font_name: str = "msyh", font_path: str = "msyh.ttc") -> None:
        """初始化生成器，注册中文字体

        Args:
            font_name: 注册后的字体名称
            font_path: 字体文件路径（系统字体名或完整路径）
        """
        self.font_name = font_name
        self._font_registered = False
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            self._font_registered = True
            logger.info(f"中文字体 '{font_name}' 注册成功")
        except Exception as e:
            self.font_name = "Helvetica"
            logger.warning(f"中文字体注册失败 ({e})，fallback 到 Helvetica")

    def generate(self, config: PDFGenConfig) -> str:
        """根据配置生成PDF，返回文件路径

        Args:
            config: PDF生成配置

        Returns:
            生成的PDF文件路径
        """
        c = canvas.Canvas(config.output_path, pagesize=A4)
        width, height = A4

        # 设置元数据
        c.setTitle(config.title)
        c.setAuthor(config.author)

        # 绘制封面
        self._draw_cover(c, config, width, height)

        # 绘制目录
        self._draw_toc(c, config.chapters, width, height)

        # 逐章绘制
        for chapter in config.chapters:
            self._draw_chapter(c, chapter, width, height)

        c.save()
        logger.info(f"PDF已生成: {os.path.abspath(config.output_path)}")
        return config.output_path

    def _draw_cover(self, c: canvas.Canvas, config: PDFGenConfig,
                    width: float, height: float) -> None:
        """绘制封面页"""
        # 标题
        self._draw_text(c, config.title, width / 2 - 120, height / 2 + 80, size=24)
        # 学科和年级
        self._draw_text(c, f"{config.subject} {config.grade}", width / 2 - 60, height / 2 + 30, size=16)
        # 作者
        self._draw_text(c, f"作者: {config.author}", width / 2 - 50, height / 2 - 10, size=12)
        # 标注
        self._draw_text(c, "AI 智能教育辅助平台 内部测试版", width / 2 - 110, height / 2 - 50, size=12)
        c.showPage()

    def _draw_toc(self, c: canvas.Canvas, chapters: list[Chapter],
                  width: float, height: float) -> None:
        """绘制目录页"""
        self._draw_text(c, "目录", width / 2 - 30, height - 80, size=20)
        y = height - 150
        for i, chapter in enumerate(chapters, start=1):
            indent = 100 if chapter.level == 1 else 130
            self._draw_text(c, f"{chapter.title} ............ {i}", indent, y, size=14)
            y -= 30
        c.showPage()

    def _draw_chapter(self, c: canvas.Canvas, chapter: Chapter,
                      width: float, height: float) -> None:
        """绘制章节页"""
        # 章节标题
        title_size = 20 if chapter.level == 1 else 16
        self._draw_text(c, chapter.title, 100, height - 80, size=title_size)

        # 正文内容
        y = height - 130
        for line in chapter.content:
            if y < 50:  # 页面底部边界
                c.showPage()
                y = height - 80
            self._draw_text(c, line, 100, y, size=12)
            y -= 25

        c.showPage()

    def _draw_text(self, c: canvas.Canvas, text: str, x: float, y: float,
                   size: int = 12) -> None:
        """绘制文本行"""
        c.setFont(self.font_name, size)
        c.drawString(x, y, text)
