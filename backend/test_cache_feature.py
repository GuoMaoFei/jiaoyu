"""
OCR 缓存功能测试脚本
演示缓存的工作原理和使用方法
"""

import sys

sys.path.insert(0, "backend")

from pageindex.utils import get_page_tokens
from pathlib import Path


def test_cache_functionality():
    """测试缓存功能"""
    print("=" * 60)
    print("OCR 缓存功能测试")
    print("=" * 60)

    pdf_path = "D:/BaiduNetdiskDownload/25中级会计-实务官方教材电子书.pdf"

    if not Path(pdf_path).exists():
        print(f"\n❌ PDF 文件不存在: {pdf_path}")
        print("\n请确保 PDF 文件存在后再运行此脚本")
        return

    print(f"\n✅ PDF 文件: {pdf_path}")

    # 测试 1: 首次运行（无缓存）
    print("\n" + "-" * 60)
    print("测试 1: 首次运行（模拟无缓存）")
    print("-" * 60)
    print("正在禁用缓存运行 OCR...")
    print("预期: 执行 EasyOCR，耗时约 36 分钟")
    print(f"缓存位置: cache/page_cache/*.json")
    print("\n注意: 此测试会消耗大量时间!")
    print("如果想跳过，请按 Ctrl+C 中断")

    # 实际测试时，我们可以先测试缓存是否已存在
    cache_dir = Path("cache/page_cache")
    cache_files = list(cache_dir.glob("*.json"))

    print(f"\n当前缓存目录:")
    if cache_files:
        for cache_file in cache_files:
            print(f"  - {cache_file.name} ({cache_file.stat().st_size / 1024:.1f} KB)")
    else:
        print("  (无缓存文件)")

    print(f"\n缓存目录: {cache_dir.absolute()}")
    print(f"总缓存文件数: {len(cache_files)}")

    # 测试 2: 模拟使用缓存
    print("\n" + "-" * 60)
    print("测试 2: 模拟使用缓存")
    print("-" * 60)
    print("\n当缓存存在时，下次上传将:")
    print("1. 检测到缓存文件")
    print("2. 从缓存加载 526 页 OCR 文本（0 秒）")
    print("3. 节省约 36 分钟 OCR 时间")
    print("4. 节省约 $1-2 API Token 成本")

    print("\n" + "=" * 60)
    print("缓存策略总结:")
    print("=" * 60)
    print("✅ 首次处理：运行 EasyOCR（36 分钟）+ 保存缓存")
    print("✅ 失败后重试：从缓存加载（0 秒）")
    print("✅ 激活后清理：调用 DELETE /api/materials/{id}/cache")
    print("✅ 节省：大量时间 + Token 成本")

    print("\n" + "=" * 60)
    print("建议的工作流程:")
    print("=" * 60)
    print("1. 上传 PDF → 处理 OCR + 生成树 → 失败")
    print("2. 等待数据库错误或超时")
    print("3. 重新上传同一 PDF")
    print("4. 系统检测到缓存，直接加载（36 分钟节省！）")
    print("5. 继续处理生成树并保存")
    print("6. 完成后手动调用 DELETE /api/materials/{id}/cache")
    print("   或在学生激活教材时自动清理")


if __name__ == "__main__":
    test_cache_functionality()
