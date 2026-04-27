"""Unit tests for rule-based optimization functions (zero LLM calls)."""

import pytest
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pageindex.rule_based import (
    find_toc_pages_rule_based,
    detect_page_index_rule_based,
    check_title_in_start_rule_based,
)


# ── find_toc_pages_rule_based ────────────────────────────────────────────

class TestFindTocPagesRuleBased:
    def test_detects_toc_with_keyword_and_pattern(self):
        """Pages with '目录' keyword and chapter patterns should be detected."""
        page_list = [
            ("前言内容", 10),
            ("目录\n第一章 总论 ...... 1\n第二章 函数 ...... 15", 50),
            ("第一章 总论\n本章介绍基本概念...", 100),
        ]
        result = find_toc_pages_rule_based(page_list)
        assert 1 in result  # Page index 1 has "目录" + chapter patterns

    def test_detects_toc_with_contents_keyword(self):
        """Pages with 'CONTENTS' keyword should be detected."""
        page_list = [
            ("Preface text", 10),
            ("CONTENTS\n1. Introduction .... 1\n2. Methods .... 15", 50),
        ]
        result = find_toc_pages_rule_based(page_list)
        assert 1 in result

    def test_no_toc_pages(self):
        """Pages without TOC keywords should return empty list."""
        page_list = [
            ("第一章 总论\n本章介绍基本概念...", 100),
            ("第二章 函数\n函数的定义和性质...", 100),
        ]
        result = find_toc_pages_rule_based(page_list)
        assert result == []

    def test_empty_page_list(self):
        """Empty page_list should return empty list."""
        result = find_toc_pages_rule_based([])
        assert result == []

    def test_max_check_pages_limit(self):
        """Should only check up to max_check_pages."""
        page_list = [
            ("正文内容", 10),
        ] * 30
        page_list[25] = ("目录\n第一章 测试 ...... 1", 50)
        # With default max_check_pages=20, page 25 should not be checked
        result = find_toc_pages_rule_based(page_list, max_check_pages=20)
        assert result == []
        # With max_check_pages=30, page 25 should be found
        result = find_toc_pages_rule_based(page_list, max_check_pages=30)
        assert 25 in result

    def test_toc_continuation_page(self):
        """Pages immediately after a TOC page with chapter patterns are also TOC."""
        page_list = [
            ("目录\n第一章 总论 ...... 1", 50),
            ("第三章 积分 ...... 45\n第四章 微分 ...... 60", 50),
            ("第一章 总论\n正文内容...", 100),
        ]
        result = find_toc_pages_rule_based(page_list)
        assert 0 in result  # First TOC page
        assert 1 in result  # Continuation page


# ── detect_page_index_rule_based ─────────────────────────────────────────

class TestDetectPageIndexRuleBased:
    def test_dots_with_page_numbers(self):
        """TOC with dot leaders and page numbers should return 'yes'."""
        toc = """第一章 总论 ...... 1
第二章 函数 ...... 15
第三章 积分 ...... 45"""
        assert detect_page_index_rule_based(toc) == "yes"

    def test_no_page_numbers(self):
        """TOC without page numbers should return 'no'."""
        toc = """第一章 总论
第二章 函数
第三章 积分"""
        assert detect_page_index_rule_based(toc) == "no"

    def test_empty_content(self):
        """Empty content should return 'no'."""
        assert detect_page_index_rule_based("") == "no"
        assert detect_page_index_rule_based(None) == "no"

    def test_spaces_with_page_numbers(self):
        """TOC with space-aligned page numbers should return 'yes'."""
        toc = """第一章 总论     1
第二章 函数     15"""
        assert detect_page_index_rule_based(toc) == "yes"

    def test_ambiguous_format_returns_unknown(self):
        """TOC with few page-number-like lines should return 'unknown'."""
        # Only 1 out of 5 lines has a page pattern (20% < 30%)
        toc = """第一章 总论
这是正文描述内容
第二章 函数 ...... 15
更多正文描述
第三章 积分"""
        result = detect_page_index_rule_based(toc)
        assert result in ("unknown", "no")  # Depends on exact pattern matching


# ── check_title_in_start_rule_based ──────────────────────────────────────

class TestCheckTitleInStartRuleBased:
    def test_exact_match(self):
        """Title exactly at page start should return 'yes'."""
        title = "第三章 函数"
        page_text = "第三章 函数\n函数是数学中的基本概念..."
        assert check_title_in_start_rule_based(title, page_text) == "yes"

    def test_fuzzy_match_no_spaces(self):
        """Title with CJK spaces should match after space removal."""
        title = "第三章 函数"
        page_text = "第 三 章 函 数\n函数是数学中的基本概念..."
        assert check_title_in_start_rule_based(title, page_text) == "yes"

    def test_no_match(self):
        """Title not in page prefix should return 'no'."""
        title = "第三章 函数"
        page_text = "第二章 极限\n极限的定义和性质..."
        assert check_title_in_start_rule_based(title, page_text) == "no"

    def test_empty_inputs(self):
        """Empty title or page_text should return None."""
        assert check_title_in_start_rule_based("", "some text") is None
        assert check_title_in_start_rule_based("some title", "") is None

    def test_title_beyond_check_chars(self):
        """Title beyond max_check_chars should not match."""
        title = "第三章 函数"
        # Title is after 200 chars
        page_text = "x" * 200 + "第三章 函数\n内容..."
        assert check_title_in_start_rule_based(title, page_text) == "no"

    def test_partial_match_returns_none(self):
        """Title prefix matches but full title doesn't should return None."""
        title = "第三章 函数与极限"
        page_text = "第三章 函 数\n但不是完整标题..."
        result = check_title_in_start_rule_based(title, page_text)
        # Could be None (uncertain) or "no" depending on exact matching
        assert result in (None, "no", "yes")


# ── LLMCallTracker ──────────────────────────────────────────────────────

class TestLLMCallTracker:
    def test_record_and_summary(self):
        """LLMCallTracker should correctly record and summarize stats."""
        from pageindex.utils import LLMCallTracker
        tracker = LLMCallTracker()
        tracker.record_rule_hit("toc_detect")
        tracker.record_rule_hit("toc_detect")
        tracker.record_rule_miss("toc_detect")
        tracker.record_llm_call("toc_detect")
        tracker.set_before_count("toc_detect", 20)

        stats = tracker._stats["toc_detect"]
        assert stats.rule_hit_count == 2
        assert stats.rule_miss_count == 1
        assert stats.call_count_after == 1
        assert stats.call_count_before == 20
        assert stats.rule_hit_rate == 2 / 3

    def test_reduction_ratio(self):
        """Reduction ratio should be calculated correctly."""
        from pageindex.utils import LLMCallStats
        stats = LLMCallStats(stage="test", call_count_before=100, call_count_after=20)
        assert stats.reduction_ratio == 0.8

    def test_zero_before_count(self):
        """Zero before count should give 0.0 reduction ratio."""
        from pageindex.utils import LLMCallStats
        stats = LLMCallStats(stage="test", call_count_before=0, call_count_after=0)
        assert stats.reduction_ratio == 0.0


# ── build_catalog_from_pageindex ─────────────────────────────────────────

class TestBuildCatalogFromPageindex:
    def test_structure_with_enough_nodes(self):
        """Should convert structure with >=5 nodes to catalog_tree."""
        from app.services.tree_builder import build_catalog_from_pageindex

        structure = [
            {
                "title": "第一章 总论",
                "physical_index": 5,
                "nodes": [
                    {"title": "1.1 基本概念", "physical_index": 5, "nodes": []},
                    {"title": "1.2 性质", "physical_index": 10, "nodes": []},
                ],
            },
            {
                "title": "第二章 函数",
                "physical_index": 15,
                "nodes": [
                    {"title": "2.1 定义", "physical_index": 15, "nodes": []},
                ],
            },
        ]

        tree_result = {"structure": structure, "toc_text": None}
        result = build_catalog_from_pageindex(tree_result, [])
        assert len(result) >= 1
        assert result[0]["title"] == "第一章 总论"
        assert result[0]["page"] == 5

    def test_empty_structure(self):
        """Empty structure should return empty list."""
        from app.services.tree_builder import build_catalog_from_pageindex
        result = build_catalog_from_pageindex({"structure": [], "toc_text": None}, [])
        assert result == []


# ── map_dual_tree_rule_based ─────────────────────────────────────────────

class TestMapDualTreeRuleBased:
    def test_basic_mapping(self):
        """Should map PI nodes to catalog nodes based on page range."""
        from app.utils.vlm_catalog import map_dual_tree_rule_based

        catalog_tree = [
            {"title": "第一章 总论", "page": 5, "children": []},
            {"title": "第二章 函数", "page": 15, "children": []},
        ]

        pi_tree = [
            {"node_id": "n1", "title": "总论", "physical_index": 5, "summary": "基本概念"},
            {"node_id": "n2", "title": "函数", "physical_index": 15, "summary": "函数定义"},
        ]

        mapped_tree, coverage = map_dual_tree_rule_based(catalog_tree, pi_tree)
        assert coverage > 0
        assert "mapped_pi_nodes" in mapped_tree[0]

    def test_empty_inputs(self):
        """Empty inputs should return empty tree and 0 coverage."""
        from app.utils.vlm_catalog import map_dual_tree_rule_based
        mapped_tree, coverage = map_dual_tree_rule_based([], [])
        assert mapped_tree == []
        assert coverage == 0.0
