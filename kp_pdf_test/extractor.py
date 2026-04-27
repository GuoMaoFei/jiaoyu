"""知识点提取器 - 从解析文本中通过LLM提取知识点，实现去重和层级构建，不依赖数据库"""

import asyncio
import json
import logging
import re
import sys
from dataclasses import asdict
from typing import List

from .models import PageResult, ExtractedKnowledgePoint

logger = logging.getLogger(__name__)

# 确保backend模块可导入
_BACKEND_ADDED = False


def _ensure_backend_path():
    """确保backend目录在sys.path中"""
    global _BACKEND_ADDED
    if not _BACKEND_ADDED:
        backend_dir = str(_find_backend_dir())
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        _BACKEND_ADDED = True


def _find_backend_dir():
    """查找backend目录"""
    from pathlib import Path
    current = Path(__file__).resolve().parent
    for parent in [current.parent, *current.parents]:
        candidate = parent / "backend"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("无法找到backend目录")


# ── LLM 提取提示词（复用kp_extractor.py的设计） ──────────────────

_KP_EXTRACT_PROMPT_TEXT = """你是一个教材知识点提取引擎。
你将收到一节教材内容。请从中提取出该节涉及的所有知识点。

输出要求：严格返回 JSON 数组，不要 markdown 代码块。
每个元素包含：
- "title": 知识点名称（简洁，如"绝对值的代数定义"）
- "summary": 一句话概括（50字以内）
- "keywords": 逗号分隔的关键词（用于检索匹配，如"绝对值,absolute value,|x|,非负性"）
- "level": 深度层级（1=知识领域, 2=主题, 3=具体概念, 4=子概念细节）
- "parent_title": 该知识点所属的上级主题名称（用于构建层级关系）
- "relevance": 该知识点在本节内容中的核心程度（0-100）

规则：
1. 粒度要细：不要把"有理数"当成一个知识点，应该拆成"有理数的定义"、"有理数的分类"等
2. keywords 必须包含该知识点的常见别称和英文术语
3. 只提取本节明确讲解的知识点，不要推测其他章节的内容
4. 通常一节内容包含 3-8 个知识点
5. title 不要带章节号前缀
6. parent_title 应该使用当前章节标题或其上级主题名称，保持与教材结构一致"""


# ── 去重工具函数 ────────────────────────────────────────────────

def _extract_bigrams(text: str) -> set[str]:
    """提取文本的bigram集合"""
    text = re.sub(r'\s+', '', text)
    return {text[i:i+2] for i in range(len(text) - 1)}


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """计算两个文本的bigram Jaccard相似度"""
    bigrams_a = _extract_bigrams(text_a)
    bigrams_b = _extract_bigrams(text_b)
    if not bigrams_a and not bigrams_b:
        return 0.0
    intersection = bigrams_a & bigrams_b
    union = bigrams_a | bigrams_b
    return len(intersection) / len(union) if union else 0.0


def _merge_keywords(kw_a: str, kw_b: str) -> str:
    """合并两个关键词字符串，去重"""
    words_a = {w.strip() for w in kw_a.split(",") if w.strip()}
    words_b = {w.strip() for w in kw_b.split(",") if w.strip()}
    merged = words_a | words_b
    return ",".join(sorted(merged))


def _normalize_title(title: str) -> str:
    """去标点、空格、章节号前缀"""
    title = re.sub(r'^[\d\.]+\s*', '', title)
    title = re.sub(r'^第[\d一二三四五六七八九十]+[章节]\s*', '', title)
    title = re.sub(r'^§[\d\.]+\s*', '', title)
    title = re.sub(r'\s+', '', title)
    return title.strip()


def _safe_str(value, sep: str = "") -> str:
    """安全地将值转为字符串，处理list/dict等类型

    Args:
        value: 任意值
        sep: 如果value是list，用此分隔符连接
    """
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return sep.join(str(v).strip() for v in value if v)
    if isinstance(value, dict):
        return str(value)
    return str(value).strip() if value else ""


class KnowledgePointTestExtractor:
    """知识点提取器（测试用，不依赖数据库）"""

    def __init__(self) -> None:
        """初始化，延迟加载LLM模型"""
        self._llm = None

    def _get_llm(self):
        """延迟获取LLM模型实例"""
        if self._llm is None:
            try:
                _ensure_backend_path()
                from app.utils.llm_router import get_medium_model
                self._llm = get_medium_model(temperature=0.1)
            except Exception as e:
                logger.error(f"LLM模型加载失败: {e}")
                raise
        return self._llm

    async def extract_from_pages(self, pages: List[PageResult]) -> List[ExtractedKnowledgePoint]:
        """从页面解析结果中提取知识点

        将相邻页面文本合并为章节，逐章节提取知识点后去重。
        """
        # 按章节分组：尝试根据标题行识别章节边界
        chapters = self._split_chapters(pages)

        all_kps = []
        sem = asyncio.Semaphore(5)

        async def _extract_one(title: str, text: str):
            async with sem:
                try:
                    kps = await self.extract_from_chapter(title, text)
                    all_kps.extend(kps)
                except Exception as e:
                    logger.warning(f"章节 '{title}' 知识点提取失败: {e}")

        await asyncio.gather(*[_extract_one(t, txt) for t, txt in chapters])

        # 去重
        deduped = self.deduplicate(all_kps)
        # 构建层级
        self.build_hierarchy(deduped)

        return deduped

    def _split_chapters(self, pages: List[PageResult]) -> list[tuple[str, str]]:
        """将页面文本按章节分割

        识别教材的"第X单元"结构，将每个单元的标题和内容正确分组。
        跳过封面页和目录页的内容。

        Returns:
            [(chapter_title, chapter_text), ...]
        """
        chapters = []
        current_title = ""
        current_lines = []
        in_content = False  # 是否已进入正文区域（跳过封面/目录）

        for page in pages:
            text = page.text.strip()
            if not text:
                continue

            lines = text.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # 检测单元标题行（"第X单元：XXX"）
                unit_match = re.match(r'^(第[一二三四五六七八九十\d]+单元[：:].+)', line)
                if unit_match:
                    in_content = True
                    # 保存前一个章节
                    if current_lines and current_title:
                        chapters.append((current_title, "\n".join(current_lines)))
                    current_title = unit_match.group(1)
                    current_lines = []
                    continue

                # 检测节标题行（"1. XXX" 或 "2. XXX"），作为当前单元的子节
                section_match = re.match(r'^(\d+\.\s.+)', line)
                if section_match and in_content:
                    # 节标题不分割章节，而是作为内容的一部分
                    # 但记录为子节标记
                    current_lines.append(line)
                    continue

                # 目录页特征：包含"............"的行
                if '............' in line or '..........' in line:
                    in_content = False  # 标记为目录区域
                    continue

                # 封面页特征：包含"内部测试版"或"作者:"
                if '内部测试版' in line or line.startswith('作者:'):
                    continue

                # 正文内容
                if in_content:
                    current_lines.append(line)

        # 保存最后一个章节
        if current_lines and current_title:
            chapters.append((current_title, "\n".join(current_lines)))

        # 如果没有识别到章节，将所有文本作为一个章节
        if not chapters:
            all_text = "\n".join(p.text for p in pages if p.text.strip())
            if all_text.strip():
                chapters.append(("全部内容", all_text))

        return chapters

    async def extract_from_chapter(self, chapter_title: str, chapter_text: str) -> List[ExtractedKnowledgePoint]:
        """从单个章节文本中提取知识点

        Args:
            chapter_title: 章节标题
            chapter_text: 章节正文

        Returns:
            提取的知识点列表
        """
        # 截断过长内容
        if len(chapter_text) > 8000:
            chapter_text = chapter_text[:8000]

        try:
            llm = self._get_llm()
            from langchain_core.prompts import ChatPromptTemplate

            prompt = ChatPromptTemplate.from_messages([
                ("system", _KP_EXTRACT_PROMPT_TEXT),
                ("human", "当前章节：{chapter_title}\n\n教材内容：\n{content}")
            ])

            chain = prompt | llm
            response = await chain.ainvoke({"chapter_title": chapter_title, "content": chapter_text})

            # 处理response.content：可能是str或list（Anthropic extended thinking格式）
            raw_content = response.content
            if isinstance(raw_content, list):
                # 从list中提取type='text'的项
                text = ""
                for block in raw_content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        break
                if not text:
                    text = str(raw_content)
            else:
                text = str(raw_content).strip()

            # 去除可能的 markdown 代码块包裹
            if text.startswith("```"):
                text = re.sub(r'^```\w*\n?', '', text)
                text = re.sub(r'\n?```$', '', text)

            items = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"章节 '{chapter_title}' LLM返回无效JSON: {e}")
            return []
        except Exception as e:
            logger.warning(f"章节 '{chapter_title}' LLM调用失败: {e}")
            return []

        result = []
        for item in items:
            if not isinstance(item, dict) or "title" not in item:
                continue
            title = _normalize_title(_safe_str(item.get("title", "")))
            if not title:
                continue
            kp = ExtractedKnowledgePoint(
                title=title,
                summary=_safe_str(item.get("summary", ""))[:100],
                keywords=_safe_str(item.get("keywords", ""), sep=","),
                level=min(4, max(1, int(item.get("level", 3)))),
                parent_title=_safe_str(item.get("parent_title", "")),
                relevance=min(100, max(0, int(item.get("relevance", 50)))),
                source_chapter=chapter_title,
            )
            result.append(kp)

        return result

    def deduplicate(self, kps: List[ExtractedKnowledgePoint]) -> List[ExtractedKnowledgePoint]:
        """bigram Jaccard去重（阈值0.8）

        保留summary更长者，合并keywords。
        """
        if len(kps) <= 1:
            return kps

        keep = []
        removed = 0
        for kp in kps:
            is_dup = False
            for existing in keep:
                sim = _jaccard_similarity(kp.title + kp.keywords, existing.title + existing.keywords)
                if sim > 0.8:
                    is_dup = True
                    if len(kp.summary) > len(existing.summary):
                        existing.summary = kp.summary
                    existing.keywords = _merge_keywords(existing.keywords, kp.keywords)
                    removed += 1
                    break
            if not is_dup:
                keep.append(kp)

        logger.info(f"去重: input={len(kps)} output={len(keep)} duplicates={removed}")
        return keep

    def build_hierarchy(self, kps: List[ExtractedKnowledgePoint]) -> List[ExtractedKnowledgePoint]:
        """根据parent_title构建层级关系

        为每个知识点设置parent_id（通过parent_title匹配其他知识点的title）。
        由于ExtractedKnowledgePoint没有parent_id字段，此方法主要验证层级关系完整性。
        """
        title_map = {kp.title: kp for kp in kps}
        orphan_count = 0
        for kp in kps:
            if kp.parent_title and kp.parent_title not in title_map:
                orphan_count += 1
        if orphan_count:
            logger.info(f"层级构建: {len(kps)} 个知识点, {orphan_count} 个的parent_title未匹配")
        return kps

    def save_result(self, kps: List[ExtractedKnowledgePoint], output_path: str) -> None:
        """将知识点保存为JSON文件"""
        import os
        data = [asdict(kp) for kp in kps]
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"知识点已保存: {output_path} ({len(kps)} 个)")
