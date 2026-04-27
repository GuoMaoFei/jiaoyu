"""端到端编排器 - 编排PDF生成→解析→知识点提取的完整流程"""

import logging
import os
import time

from .models import E2EResult, ParseResult, ExtractedKnowledgePoint
from .generator import PDFGenerator
from .parser import PDFParser
from .extractor import KnowledgePointTestExtractor
from .templates import get_template

logger = logging.getLogger(__name__)


class E2ERunner:
    """端到端测试编排器"""

    def __init__(self) -> None:
        self.generator = PDFGenerator()
        self.parser = PDFParser()
        self.extractor = KnowledgePointTestExtractor()
        self._stage_results: dict = {}

    async def run(self, template: str = "math_grade1", stage: str = "all",
                  output_dir: str = "./test_output") -> E2EResult:
        """执行端到端测试

        Args:
            template: 教材模板名称
            stage: 执行阶段 (all/generate/parse/extract)
            output_dir: 输出目录

        Returns:
            E2EResult 包含各阶段结果
        """
        os.makedirs(output_dir, exist_ok=True)
        self._stage_results = {}

        result = E2EResult(pdf_path="")
        total_start = time.time()

        # ── 生成阶段 ──────────────────────────────────────────
        if stage in ("all", "generate"):
            try:
                pdf_path = await self._run_generate(template, output_dir)
                result.pdf_path = pdf_path
            except Exception:
                result.stage_results = dict(self._stage_results)
                result.total_duration = time.time() - total_start
                return result
        else:
            result.pdf_path = os.path.join(output_dir, "test_output.pdf")

        # ── 解析阶段 ──────────────────────────────────────────
        if stage in ("all", "parse"):
            try:
                parse_result = await self._run_parse(result.pdf_path, output_dir)
                result.parse_result = parse_result
            except Exception:
                result.stage_results = dict(self._stage_results)
                result.total_duration = time.time() - total_start
                return result

        # ── 提取阶段 ──────────────────────────────────────────
        if stage in ("all", "extract"):
            if result.parse_result is None:
                json_path = os.path.join(output_dir, "parse_result.json")
                if os.path.exists(json_path):
                    result.parse_result = self._load_parse_result(json_path)
                else:
                    logger.warning("提取阶段需要解析结果，但未找到。请先执行parse阶段。")
                    self._record_stage("extract", "skipped", 0, "缺少解析结果")

            if result.parse_result is not None:
                try:
                    kps = await self._run_extract(result.parse_result, output_dir)
                    result.knowledge_points = kps
                except Exception:
                    pass

        result.stage_results = dict(self._stage_results)
        result.total_duration = time.time() - total_start
        return result

    async def _run_generate(self, template: str, output_dir: str) -> str:
        """执行生成阶段"""
        start = time.time()
        try:
            config = get_template(template)
            config.output_path = os.path.join(output_dir, "test_output.pdf")
            pdf_path = self.generator.generate(config)
            duration = time.time() - start
            self._record_stage("generate", "success", duration)
            logger.info(f"生成阶段完成: {pdf_path} ({duration:.2f}s)")
            return pdf_path
        except Exception as e:
            duration = time.time() - start
            self._record_stage("generate", "failed", duration, str(e))
            raise

    async def _run_parse(self, pdf_path: str, output_dir: str) -> ParseResult:
        """执行解析阶段"""
        start = time.time()
        try:
            parse_result = self.parser.parse(pdf_path, "pymupdf")
            json_path = os.path.join(output_dir, "parse_result.json")
            self.parser.save_result(parse_result, json_path)
            duration = time.time() - start
            self._record_stage("parse", "success", duration)
            logger.info(f"解析阶段完成: {len(parse_result.pages)}页, {parse_result.total_chars}字符 ({duration:.2f}s)")
            return parse_result
        except Exception as e:
            duration = time.time() - start
            self._record_stage("parse", "failed", duration, str(e))
            raise

    async def _run_extract(self, parse_result: ParseResult,
                           output_dir: str) -> list[ExtractedKnowledgePoint]:
        """执行提取阶段"""
        start = time.time()
        try:
            kps = await self.extractor.extract_from_pages(parse_result.pages)
            json_path = os.path.join(output_dir, "kps.json")
            self.extractor.save_result(kps, json_path)
            duration = time.time() - start
            self._record_stage("extract", "success", duration)
            logger.info(f"提取阶段完成: {len(kps)}个知识点 ({duration:.2f}s)")
            return kps
        except Exception as e:
            duration = time.time() - start
            self._record_stage("extract", "failed", duration, str(e))
            raise

    def _record_stage(self, stage: str, status: str, duration: float,
                      error: str | None = None) -> None:
        """记录阶段执行状态"""
        self._stage_results[stage] = {
            "status": status,
            "duration": round(duration, 3),
        }
        if error:
            self._stage_results[stage]["error"] = error

    def _load_parse_result(self, json_path: str) -> ParseResult | None:
        """从JSON文件加载解析结果"""
        import json
        from .models import PageResult
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            pages = [PageResult(**p) for p in data.get("pages", [])]
            return ParseResult(
                pages=pages,
                strategy=data.get("strategy", ""),
                total_tokens=data.get("total_tokens", 0),
                total_chars=data.get("total_chars", 0),
                pdf_path=data.get("pdf_path", ""),
            )
        except Exception as e:
            logger.warning(f"加载解析结果失败: {e}")
            return None
