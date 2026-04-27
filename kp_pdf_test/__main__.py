"""CLI命令行入口 - 使用argparse提供generate/parse/extract/e2e/info子命令"""

import argparse
import asyncio
import json
import logging
import sys

from .models import PageResult, ParseResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def cmd_generate(args):
    """生成测试PDF"""
    from .generator import PDFGenerator
    from .templates import get_template

    gen = PDFGenerator()
    config = get_template(args.template)
    if args.title:
        config.title = args.title
    if args.author:
        config.author = args.author
    config.output_path = args.output

    path = gen.generate(config)
    print(f"PDF已生成: {path}")


def cmd_parse(args):
    """解析PDF文件"""
    from .parser import PDFParser

    parser = PDFParser()

    if args.compare:
        # 策略对比模式
        report = parser.compare_strategies(args.input)
        print("=== 策略对比报告 ===")
        for name, data in report.items():
            print(f"\n[{name}]")
            print(f"  总字符数: {data['total_chars']}")
            print(f"  总token数: {data['total_tokens']}")
            print(f"  逐页字符数: {data['page_lengths']}")
        return

    if args.strategy == "all":
        # 全策略解析
        results = parser.parse_all(args.input)
        for name, result in results.items():
            print(f"\n[{name}] {len(result.pages)}页, {result.total_chars}字符, {result.total_tokens}tokens")
            out_path = args.output.replace(".json", f"_{name}.json")
            parser.save_result(result, out_path)
            print(f"  已保存: {out_path}")
    else:
        result = parser.parse(args.input, args.strategy)
        print(f"解析完成: {len(result.pages)}页, {result.total_chars}字符, {result.total_tokens}tokens")
        parser.save_result(result, args.output)
        print(f"已保存: {args.output}")


def cmd_extract(args):
    """提取知识点"""
    from .extractor import KnowledgePointTestExtractor

    # 从JSON加载解析结果
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    pages = [PageResult(**p) for p in data.get("pages", [])]

    ext = KnowledgePointTestExtractor()
    kps = asyncio.run(ext.extract_from_pages(pages))

    ext.save_result(kps, args.output)
    print(f"提取完成: {len(kps)}个知识点, 已保存: {args.output}")


def cmd_e2e(args):
    """端到端测试"""
    from .e2e_runner import E2ERunner

    runner = E2ERunner()
    result = asyncio.run(runner.run(
        template=args.template,
        stage=args.stage,
        output_dir=args.output_dir,
    ))

    print("\n=== 端到端测试结果 ===")
    print(f"PDF路径: {result.pdf_path}")
    if result.parse_result:
        pr = result.parse_result
        print(f"解析: {len(pr.pages)}页, {pr.total_chars}字符, {pr.total_tokens}tokens")
    print(f"知识点: {len(result.knowledge_points)}个")
    print(f"各阶段状态:")
    for stage, info in result.stage_results.items():
        status = info["status"]
        duration = info.get("duration", 0)
        error = info.get("error", "")
        line = f"  {stage}: {status} ({duration:.3f}s)"
        if error:
            line += f" - {error}"
        print(line)
    print(f"总耗时: {result.total_duration:.2f}s")


def cmd_info(args):
    """PDF基本信息"""
    from .parser import PDFParser

    parser = PDFParser()
    info = parser.get_info(args.input)
    print(f"文件: {args.input}")
    print(f"页数: {info['total_pages']}")
    print(f"标题: {info['title']}")
    print(f"文件大小: {info['file_size']} 字节")


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        prog="kp_pdf_test",
        description="PDF生成、解析、知识点提取测试工具链",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用子命令")

    # ── generate ──────────────────────────────────────────────
    gen_parser = subparsers.add_parser("generate", help="生成测试PDF")
    gen_parser.add_argument("--template", default="math_grade1",
                            choices=["math_grade1", "math_grade3", "chinese_grade2"],
                            help="教材模板 (默认: math_grade1)")
    gen_parser.add_argument("--output", default="test_output.pdf",
                            help="输出PDF路径 (默认: test_output.pdf)")
    gen_parser.add_argument("--title", default=None, help="自定义标题")
    gen_parser.add_argument("--author", default=None, help="自定义作者")
    gen_parser.set_defaults(func=cmd_generate)

    # ── parse ─────────────────────────────────────────────────
    parse_parser = subparsers.add_parser("parse", help="解析PDF文件")
    parse_parser.add_argument("--input", required=True, help="输入PDF文件路径")
    parse_parser.add_argument("--strategy", default="pymupdf",
                              choices=["pypdf2", "pymupdf", "all"],
                              help="解析策略 (默认: pymupdf)")
    parse_parser.add_argument("--output", default="parse_result.json",
                              help="输出JSON路径 (默认: parse_result.json)")
    parse_parser.add_argument("--compare", action="store_true",
                              help="对比所有策略的解析结果")
    parse_parser.set_defaults(func=cmd_parse)

    # ── extract ───────────────────────────────────────────────
    ext_parser = subparsers.add_parser("extract", help="提取知识点")
    ext_parser.add_argument("--input", required=True,
                            help="输入解析结果JSON路径")
    ext_parser.add_argument("--output", default="kps.json",
                            help="输出知识点JSON路径 (默认: kps.json)")
    ext_parser.set_defaults(func=cmd_extract)

    # ── e2e ───────────────────────────────────────────────────
    e2e_parser = subparsers.add_parser("e2e", help="端到端测试")
    e2e_parser.add_argument("--template", default="math_grade1",
                            choices=["math_grade1", "math_grade3", "chinese_grade2"],
                            help="教材模板 (默认: math_grade1)")
    e2e_parser.add_argument("--stage", default="all",
                            choices=["all", "generate", "parse", "extract"],
                            help="执行阶段 (默认: all)")
    e2e_parser.add_argument("--output-dir", default="./test_output",
                            help="输出目录 (默认: ./test_output)")
    e2e_parser.set_defaults(func=cmd_e2e)

    # ── info ──────────────────────────────────────────────────
    info_parser = subparsers.add_parser("info", help="PDF基本信息")
    info_parser.add_argument("--input", required=True, help="PDF文件路径")
    info_parser.set_defaults(func=cmd_info)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
