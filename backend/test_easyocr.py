#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 EasyOCR 解析扫描版 PDF
"""

import sys

sys.path.insert(0, "pageindex")

from utils import get_page_tokens
import time


def test_easyocr():
    pdf_path = "D:/BaiduNetdiskDownload/25中级会计-实务官方教材电子书.pdf"

    print("=" * 60)
    print("EasyOCR 扫描版 PDF 解析测试")
    print("=" * 60)
    print(f"PDF 路径: {pdf_path}")
    print(f"GPU 信息: NVIDIA GeForce RTX 5060 Ti (16GB)")
    print(f"处理模式: CPU (当前 PyTorch 版本不完全支持 RTX 5060 Ti)")
    print("=" * 60)
    print()

    # 预估时间
    print("开始解析...")
    start_time = time.time()

    page_list = get_page_tokens(pdf_path)

    elapsed_time = time.time() - start_time

    # 统计信息
    total_pages = len(page_list)
    total_chars = sum(len(text) for text, tokens in page_list)
    avg_chars = total_chars / total_pages if total_pages > 0 else 0

    print()
    print("=" * 60)
    print("解析完成！")
    print("=" * 60)
    print(f"总页数: {total_pages}")
    print(f"总耗时: {elapsed_time:.2f} 秒 ({elapsed_time / 60:.1f} 分钟)")
    print(f"平均每页: {elapsed_time / total_pages:.2f} 秒")
    print(f"总字符数: {total_chars:,}")
    print(f"平均每页: {avg_chars:.1f} 字符")
    print()

    # 前 5 页预览
    print("前 5 页内容预览:")
    print("-" * 60)
    for i in range(min(5, total_pages)):
        text, tokens = page_list[i]
        print(f"\n第 {i + 1} 页:")
        print(f"  字符数: {len(text)}")
        print(f"  Tokens: {tokens}")
        print(f"  内容: {text[:100] if len(text) > 100 else text}")


if __name__ == "__main__":
    test_easyocr()
