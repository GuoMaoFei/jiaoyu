"""Rule-based optimization functions for PageIndex (zero LLM calls)."""

import re


def find_toc_pages_rule_based(page_list, max_check_pages=20):
    """Rule-based TOC page detection using keyword + pattern matching.

    Replaces per-page LLM calls in find_toc_pages() for the common case.

    Args:
        page_list: [(text, tokens), ...] cached per-page text
        max_check_pages: max pages to check from the start

    Returns:
        List[int]: detected TOC page indices (0-based), empty if none found
    """
    toc_keywords = ["目录", "目  录", "目次", "CONTENTS", "Contents", "contents"]
    toc_pages = []
    last_toc_idx = None

    for i in range(min(max_check_pages, len(page_list))):
        text = page_list[i][0]
        keyword_found = False
        for kw in toc_keywords:
            if kw in text:
                keyword_found = True
                break

        if keyword_found:
            has_toc_pattern = bool(
                re.search(r'第[一二三四五六七八九十零百\d]+[章节单元课组]', text)
                or re.search(r'[\.…·…—─\-]{3,}\s*\d+', text)
                or re.search(r'\d+\.\d+', text)
            )
            if has_toc_pattern or len(text.strip()) < 2000:
                toc_pages.append(i)
                last_toc_idx = i
            continue

        if last_toc_idx is not None and i == last_toc_idx + 1:
            has_chapter = bool(re.search(r'第[一二三四五六七八九十零百\d]+[章节单元课组]', text))
            has_dots_page = bool(re.search(r'[\.…·…—─\-]{3,}\s*\d+\s*$', text, re.MULTILINE))
            if has_chapter or has_dots_page:
                toc_pages.append(i)
                last_toc_idx = i
                continue
            break

    return toc_pages


def detect_page_index_rule_based(toc_content):
    """Rule-based detection of page numbers in TOC text.

    Args:
        toc_content: TOC text content

    Returns:
        "yes" | "no" | "unknown"
    """
    if not toc_content or not toc_content.strip():
        return "no"

    lines = toc_content.strip().split('\n')
    if not lines:
        return "no"

    # Pattern 1: dots/dashes followed by page number (e.g. "title...12")
    pat_dots = re.compile(r'[\.…·…—─\-]{3,}\s*\d+\s*$')
    # Pattern 2: 4+ spaces then page number (e.g. "title    12")
    pat_spaces = re.compile(r'\s{4,}\d+\s*$')
    # Pattern 3: tab then page number (e.g. "title\t12")
    pat_tab = re.compile(r'\t\d+\s*$')
    # Pattern 4: chapter/section with page number (e.g. "第1章 xxx 12")
    pat_chapter = re.compile(r'第[一二三四五六七八九十\d]+[章节].*?\d+\s*$')
    # Pattern 5: author slash then page number (e.g. "标题/作者 12")
    pat_author_page = re.compile(r'[/／]\S+\s+\d{1,4}\s*$')
    # Pattern 6: unit with page number (e.g. "第二单元 31")
    pat_unit_page = re.compile(r'第[一二三四五六七八九十\d]+单元\s*\d{1,4}\s*$')
    # Pattern 7: standalone number on its own line (common in Chinese textbooks)
    pat_standalone_num = re.compile(r'^\s*\d{1,4}\s*$')

    patterns = [pat_dots, pat_spaces, pat_tab, pat_chapter, pat_author_page, pat_unit_page]

    matched_lines = 0
    total_lines = 0
    standalone_num_lines = 0

    for line in lines:
        line = line.strip()
        if not line or len(line) < 2:
            continue
        total_lines += 1

        # Check standalone number lines separately
        if pat_standalone_num.search(line):
            standalone_num_lines += 1
            continue

        for pat in patterns:
            if pat.search(line):
                matched_lines += 1
                break

    if total_lines == 0:
        return "no"

    # If many standalone numbers appear alongside other matched patterns,
    # they are likely page numbers too
    # Also: if standalone numbers are frequent AND we have at least 1 pattern match,
    # treat standalone numbers as page indicators
    if matched_lines > 0 and standalone_num_lines >= 3:
        effective_matched = matched_lines + standalone_num_lines
    else:
        effective_matched = matched_lines + min(standalone_num_lines, matched_lines * 3)
    ratio = effective_matched / total_lines
    if ratio > 0.3:
        return "yes"
    elif matched_lines == 0 and standalone_num_lines == 0:
        return "no"
    else:
        return "unknown"


def check_title_in_start_rule_based(title, page_text, max_check_chars=200):
    """Rule-based check if a section title starts at the beginning of a page.

    Args:
        title: section title
        page_text: page text content
        max_check_chars: check only the first N characters of page_text

    Returns:
        "yes" | "no" | None  (None means uncertain, fallback to LLM)
    """
    if not title or not page_text:
        return None

    clean_title = re.sub(r' {2,}', ' ', title)
    clean_title = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', clean_title)
    clean_title = clean_title.strip()

    prefix = page_text[:max_check_chars]

    if clean_title in prefix:
        return "yes"

    title_no_space = re.sub(r'\s+', '', clean_title)
    prefix_no_space = re.sub(r'\s+', '', prefix)
    if title_no_space and title_no_space in prefix_no_space:
        return "yes"

    if len(clean_title) >= 4:
        title_prefix = clean_title[:4]
        title_prefix_no_space = re.sub(r'\s+', '', title_prefix)
        if title_prefix_no_space in prefix_no_space and title_no_space not in prefix_no_space:
            return None

    return "no"
