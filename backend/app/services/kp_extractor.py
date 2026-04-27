"""
KnowledgePointExtractor: 从教材 KnowledgeNode 内容中提取概念级知识点，
通过三级去重后创建/复用 KnowledgePoint + KnowledgePointMapping。
"""
import hashlib
import json
import logging
import re
import traceback
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.prompts import ChatPromptTemplate

from app.models.material import Material, KnowledgeNode, KnowledgeContent
from app.models.knowledge_point import KnowledgePoint, KnowledgePointMapping
from app.utils.llm_router import get_medium_model
from app.agent.tools.candidate_filter import _extract_bigrams

logger = logging.getLogger(__name__)

# ── LLM 提取提示词 ──────────────────────────────────────────────

_KP_EXTRACT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是一个教材知识点提取引擎。
你将收到一节教材内容（markdown格式）。请从中提取出该节涉及的所有知识点。

输出要求：严格返回 JSON 数组，不要 markdown 代码块。
每个元素包含：
- "title": 知识点名称（简洁，如"绝对值的代数定义"）
- "summary": 一句话概括（50字以内）
- "keywords": 逗号分隔的关键词（用于检索匹配，如"绝对值,absolute value,|x|,非负性"）
- "level": 深度层级（1=知识领域, 2=主题, 3=具体概念, 4=子概念细节）
- "parent_title": 该知识点所属的上级主题名称（用于构建层级关系）
- "relevance": 该知识点在本节内容中的核心程度（0-100）

规则：
1. 粒度要细：不要把"有理数"当成一个知识点，应该拆成"有理数的定义"、"有理数的分类"、"有理数的大小比较"等
2. keywords 必须包含该知识点的常见别称和英文术语
3. 只提取本节明确讲解的知识点，不要推测其他章节的内容
4. 通常一节内容包含 3-8 个知识点
5. title 不要带章节号前缀"""),
    ("human", "教材内容：\n{content}")
])

_KP_DEDUP_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "你是一个知识点去重判断引擎。判断两个知识点是否指同一概念。只回答 YES 或 NO。"),
    ("human", "知识点A：{title_a}\n摘要A：{summary_a}\n关键词A：{keywords_a}\n\n知识点B：{title_b}\n摘要B：{summary_b}\n关键词B：{keywords_b}\n\n这两个知识点是否指同一概念？")
])


@dataclass
class ExtractedKP:
    """LLM 提取出的单个知识点"""
    title: str
    summary: str
    keywords: str
    level: int
    parent_title: str
    relevance: int
    embedding_hash: str = ""


class KnowledgePointExtractor:
    """知识点提取器"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = get_medium_model(temperature=0.1)

    # ── 主入口 ──────────────────────────────────────────────────

    async def extract_for_material(self, material_id: str) -> Dict[str, Any]:
        """
        从教材的所有叶节点中提取知识点。
        返回统计摘要。
        """
        # 0. 查询 Material 获取 subject
        mat_result = await self.db.execute(
            select(Material).where(Material.id == material_id)
        )
        material = mat_result.scalar_one_or_none()
        if not material:
            raise ValueError(f"Material {material_id} not found")
        subject = material.subject

        # 1. 清理旧映射（重复解析同一教材时）
        await self._cleanup_old_mappings(material_id)

        # 2. 查询所有叶节点 KnowledgeNode（有 KnowledgeContent 的）
        nodes_result = await self.db.execute(
            select(KnowledgeNode)
            .where(KnowledgeNode.material_id == material_id)
            .order_by(KnowledgeNode.seq_num)
        )
        all_nodes = nodes_result.scalars().all()

        # 只处理有内容的节点
        leaf_nodes = []
        for node in all_nodes:
            content_result = await self.db.execute(
                select(KnowledgeContent).where(KnowledgeContent.knowledge_node_id == node.id)
            )
            contents = content_result.scalars().all()
            if contents:
                leaf_nodes.append((node, contents))

        if not leaf_nodes:
            logger.warning(f"[KP_EXTRACT] material={material_id} no leaf nodes with content")
            return {"extracted": 0, "new": 0, "reused": 0}

        # 3. 并发提取（Semaphore(5)）
        import asyncio
        sem = asyncio.Semaphore(5)
        all_extracted: List[Tuple[KnowledgeNode, List[ExtractedKP]]] = []

        async def _extract_one(node: KnowledgeNode, contents: list):
            async with sem:
                try:
                    combined_content = "\n\n".join(c.content_md for c in contents)
                    kps = await self._llm_extract(combined_content)
                    if kps:
                        logger.info(f"[KP_EXTRACT] material={material_id} node={node.id} extracted={len(kps)}")
                    all_extracted.append((node, kps))
                except Exception as e:
                    logger.warning(f"[KP_EXTRACT] material={material_id} node={node.id} failed: {e}")
                    all_extracted.append((node, []))

        await asyncio.gather(*[_extract_one(n, c) for n, c in leaf_nodes])

        # 4. 三级去重
        flat_kps: List[ExtractedKP] = []
        for _, kps in all_extracted:
            flat_kps.extend(kps)

        # Phase 1: 节点内 bigram 去重
        flat_kps = self._dedup_level1_intra_node(flat_kps)

        # Phase 2: hash 去重 + Phase 3: LLM 语义去重
        new_kps, reuse_pairs = await self._dedup_level2_and_3(flat_kps, subject)

        # 5. 创建知识点和映射
        stats = await self._create_points_and_mappings(
            new_kps, reuse_pairs, subject, all_extracted
        )

        # 6. 构建父子关系
        await self._build_hierarchy(subject)

        logger.info(
            f"[KP_EXTRACT] material={material_id} done: "
            f"extracted={len(flat_kps)} new={stats['new']} reused={stats['reused']}"
        )
        return stats

    # ── LLM 提取 ───────────────────────────────────────────────

    async def _llm_extract(self, content: str) -> List[ExtractedKP]:
        """调用 LLM 从内容中提取知识点列表"""
        # 截断过长内容
        if len(content) > 8000:
            content = content[:8000]

        chain = _KP_EXTRACT_PROMPT | self.llm
        response = await chain.ainvoke({"content": content})

        raw_content = response.content
        if isinstance(raw_content, list):
            text = "".join(
                part if isinstance(part, str) else part.get("text", "")
                for part in raw_content
            )
        else:
            text = str(raw_content)
        text = text.strip()
        # 去除可能的 markdown 代码块包裹
        if text.startswith("```"):
            text = re.sub(r'^```\w*\n?', '', text)
            text = re.sub(r'\n?```$', '', text)

        try:
            items = json.loads(text)
        except json.JSONDecodeError:
            logger.warning(f"[KP_EXTRACT] LLM returned invalid JSON: {text[:200]}")
            return []

        result = []
        for item in items:
            if not isinstance(item, dict) or "title" not in item:
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            normalized = self._normalize_title(title)
            kp = ExtractedKP(
                title=normalized,
                summary=str(item.get("summary", "")).strip()[:100],
                keywords=str(item.get("keywords", "")).strip(),
                level=int(item.get("level", 3)),
                parent_title=str(item.get("parent_title", "")).strip(),
                relevance=min(100, max(0, int(item.get("relevance", 50)))),
                embedding_hash=self._compute_hash(normalized),
            )
            result.append(kp)
        return result

    # ── 标题标准化与哈希 ────────────────────────────────────────

    @staticmethod
    def _normalize_title(title: str) -> str:
        """去标点、空格、章节号前缀"""
        # 去除章节号前缀如 "1.2 ", "第1节 ", "§1.2 "
        title = re.sub(r'^[\d\.]+\s*', '', title)
        title = re.sub(r'^第[\d一二三四五六七八九十]+[章节]\s*', '', title)
        title = re.sub(r'^§[\d\.]+\s*', '', title)
        # 去除多余空格
        title = re.sub(r'\s+', '', title)
        return title.strip()

    @staticmethod
    def _compute_hash(title: str) -> str:
        """SHA256[:32]"""
        return hashlib.sha256(title.encode("utf-8")).hexdigest()[:32]

    # ── 三级去重 ────────────────────────────────────────────────

    def _dedup_level1_intra_node(self, kps: List[ExtractedKP]) -> List[ExtractedKP]:
        """Phase 1: 节点内 bigram 去重，阈值 0.8"""
        if len(kps) <= 1:
            return kps

        keep = []
        removed = 0
        for kp in kps:
            is_dup = False
            for existing in keep:
                sim = self._jaccard_similarity(kp.title + kp.keywords, existing.title + existing.keywords)
                if sim > 0.8:
                    is_dup = True
                    # 保留 summary 更长者，合并 keywords
                    if len(kp.summary) > len(existing.summary):
                        existing.summary = kp.summary
                    existing.keywords = self._merge_keywords(existing.keywords, kp.keywords)
                    removed += 1
                    break
            if not is_dup:
                keep.append(kp)

        logger.info(f"[KP_DEDUP] level=1 input={len(kps)} output={len(keep)} duplicates={removed}")
        return keep

    async def _dedup_level2_and_3(
        self, kps: List[ExtractedKP], subject: str
    ) -> Tuple[List[ExtractedKP], List[Tuple[ExtractedKP, str]]]:
        """
        Phase 2: embedding_hash 去重
        Phase 3: LLM 语义去重（Jaccard 0.4~0.7 时触发）
        返回 (新知识点列表, 复用对列表[(ExtractedKP, existing_kp_id)])
        """
        # 查询同学科已有知识点的 hash
        existing_result = await self.db.execute(
            select(KnowledgePoint.id, KnowledgePoint.embedding_hash, KnowledgePoint.title,
                   KnowledgePoint.summary, KnowledgePoint.keywords, KnowledgePoint.parent_id)
            .where(KnowledgePoint.subject == subject)
        )
        existing_rows = existing_result.all()
        hash_map: Dict[str, str] = {}  # hash -> kp_id
        existing_by_id: Dict[str, Dict] = {}
        for row in existing_rows:
            if row.embedding_hash:
                hash_map[row.embedding_hash] = row.id
            existing_by_id[row.id] = {
                "id": row.id,
                "title": row.title,
                "summary": row.summary or "",
                "keywords": row.keywords or "",
                "parent_id": row.parent_id,
            }

        new_kps: List[ExtractedKP] = []
        reuse_pairs: List[Tuple[ExtractedKP, str]] = []
        llm_checks = 0

        for kp in kps:
            # Phase 2: hash 精确匹配
            if kp.embedding_hash in hash_map:
                existing_id = hash_map[kp.embedding_hash]
                reuse_pairs.append((kp, existing_id))
                continue

            # Phase 2.5: keywords Jaccard 相似度
            best_match_id = None
            best_sim = 0.0
            for eid, edata in existing_by_id.items():
                sim = self._jaccard_similarity(
                    kp.title + kp.keywords,
                    edata["title"] + edata["keywords"]
                )
                if sim > best_sim:
                    best_sim = sim
                    best_match_id = eid

            if best_sim > 0.7 and best_match_id:
                # 高相似度，直接合并
                reuse_pairs.append((kp, best_match_id))
                # 追加 keywords
                existing = existing_by_id[best_match_id]
                existing["keywords"] = self._merge_keywords(existing["keywords"], kp.keywords)
            elif 0.4 <= best_sim <= 0.7 and best_match_id and llm_checks < 10:
                # Phase 3: LLM 验证
                llm_checks += 1
                is_dup = await self._verify_duplicate_llm(kp, existing_by_id[best_match_id])
                if is_dup:
                    reuse_pairs.append((kp, best_match_id))
                    existing = existing_by_id[best_match_id]
                    existing["keywords"] = self._merge_keywords(existing["keywords"], kp.keywords)
                else:
                    new_kps.append(kp)
            else:
                new_kps.append(kp)

        logger.info(
            f"[KP_DEDUP] level=2+3 input={len(kps)} new={len(new_kps)} "
            f"reused={len(reuse_pairs)} llm_checks={llm_checks}"
        )
        return new_kps, reuse_pairs

    async def _verify_duplicate_llm(
        self, new_kp: ExtractedKP, existing: Dict
    ) -> bool:
        """Phase 3: LLM 验证两个知识点是否指同一概念"""
        try:
            chain = _KP_DEDUP_PROMPT | self.llm
            response = await chain.ainvoke({
                "title_a": new_kp.title,
                "summary_a": new_kp.summary,
                "keywords_a": new_kp.keywords,
                "title_b": existing["title"],
                "summary_b": existing["summary"],
                "keywords_b": existing["keywords"],
            })
            raw = response.content
            if isinstance(raw, list):
                answer_text = "".join(
                    p if isinstance(p, str) else p.get("text", "") for p in raw
                )
            else:
                answer_text = str(raw)
            answer = answer_text.strip().upper()
            return answer.startswith("YES")
        except Exception as e:
            logger.warning(f"[KP_DEDUP] LLM verify failed: {e}")
            return False

    # ── 创建知识点和映射 ────────────────────────────────────────

    async def _create_points_and_mappings(
        self,
        new_kps: List[ExtractedKP],
        reuse_pairs: List[Tuple[ExtractedKP, str]],
        subject: str,
        all_extracted: List[Tuple[KnowledgeNode, List[ExtractedKP]]],
    ) -> Dict[str, int]:
        """创建新 KnowledgePoint、复用已有知识点、创建 Mapping"""
        new_count = 0
        reuse_count = 0

        # 构建 title -> kp_id 映射（用于后续 mapping 创建）
        title_to_kp_id: Dict[str, str] = {}

        # 创建新知识点
        for kp in new_kps:
            point = KnowledgePoint(
                subject=subject,
                title=kp.title,
                summary=kp.summary,
                keywords=kp.keywords,
                level=kp.level,
                parent_title=kp.parent_title or None,
                embedding_hash=kp.embedding_hash,
                source_count=1,
            )
            self.db.add(point)
            await self.db.flush()
            title_to_kp_id[kp.title] = point.id
            new_count += 1

        # 复用已有知识点：递增 source_count
        for kp, existing_id in reuse_pairs:
            await self.db.execute(
                update(KnowledgePoint)
                .where(KnowledgePoint.id == existing_id)
                .values(source_count=KnowledgePoint.source_count + 1)
            )
            # 合并 keywords
            existing_result = await self.db.execute(
                select(KnowledgePoint).where(KnowledgePoint.id == existing_id)
            )
            existing_point = existing_result.scalar_one_or_none()
            if existing_point:
                merged = self._merge_keywords(existing_point.keywords or "", kp.keywords)
                existing_point.keywords = merged
            title_to_kp_id[kp.title] = existing_id
            reuse_count += 1

        await self.db.flush()

        # 创建 Mapping：遍历每个节点的提取结果
        for node, extracted_list in all_extracted:
            for ekp in extracted_list:
                kp_id = title_to_kp_id.get(ekp.title)
                if not kp_id:
                    continue
                # 检查唯一约束
                existing_mapping = await self.db.execute(
                    select(KnowledgePointMapping).where(
                        KnowledgePointMapping.knowledge_point_id == kp_id,
                        KnowledgePointMapping.knowledge_node_id == node.id,
                    )
                )
                if existing_mapping.scalar_one_or_none():
                    continue
                mapping = KnowledgePointMapping(
                    knowledge_point_id=kp_id,
                    knowledge_node_id=node.id,
                    relevance_score=ekp.relevance,
                    context_snippet=ekp.summary or None,
                )
                self.db.add(mapping)

        await self.db.flush()
        return {"new": new_count, "reused": reuse_count, "extracted": new_count + reuse_count}

    # ── 构建层级关系 ────────────────────────────────────────────

    async def _build_hierarchy(self, subject: str) -> None:
        """根据 parent_title 精确构建知识点父子关系"""
        result = await self.db.execute(
            select(KnowledgePoint).where(KnowledgePoint.subject == subject)
        )
        all_points = result.scalars().all()

        # 构建 title -> id 映射（精确匹配）
        title_to_id: Dict[str, str] = {p.title: p.id for p in all_points}

        # 构建 level -> points 索引（用于模糊匹配 fallback）
        level_map: Dict[int, List[KnowledgePoint]] = {}
        for p in all_points:
            level_map.setdefault(p.level, []).append(p)

        for point in all_points:
            if point.parent_id:
                continue  # 已有父节点，跳过

            if point.parent_title:
                # Phase 1: 精确匹配 parent_title
                parent_id = title_to_id.get(point.parent_title)
                if parent_id and parent_id != point.id:
                    point.parent_id = parent_id
                    continue

                # Phase 2: 在同级 level-1 中模糊匹配（宽松阈值 0.5）
                if point.level > 1:
                    parent_candidates = level_map.get(point.level - 1, [])
                    best_match = None
                    best_sim = 0.0
                    for cand in parent_candidates:
                        if cand.id == point.id:
                            continue
                        sim = self._jaccard_similarity(point.parent_title, cand.title)
                        if sim > best_sim:
                            best_sim = sim
                            best_match = cand
                    if best_match and best_sim > 0.5:
                        point.parent_id = best_match.id

        await self.db.flush()

    # ── 材料删除时的清理 ────────────────────────────────────────

    async def cleanup_for_material(self, material_id: str) -> Dict[str, int]:
        """清理教材关联的知识点映射和孤立知识点"""
        # 1. 查询该 material 所有 KnowledgeNode 的 id
        nodes_result = await self.db.execute(
            select(KnowledgeNode.id).where(KnowledgeNode.material_id == material_id)
        )
        node_ids = [row[0] for row in nodes_result.all()]

        if not node_ids:
            return {"mappings_deleted": 0, "points_decremented": 0, "points_deleted": 0}

        # 2. 查询关联的 KnowledgePointMapping
        mappings_result = await self.db.execute(
            select(KnowledgePointMapping).where(
                KnowledgePointMapping.knowledge_node_id.in_(node_ids)
            )
        )
        mappings = mappings_result.scalars().all()

        # 收集涉及的 knowledge_point_id
        kp_ids = set(m.knowledge_point_id for m in mappings)

        # 3. 删除 mappings
        for m in mappings:
            await self.db.delete(m)

        # 4. 重新计算 source_count
        points_decremented = 0
        points_deleted = 0
        for kp_id in kp_ids:
            # 计算剩余 mapping 数量
            count_result = await self.db.execute(
                select(func.count()).select_from(KnowledgePointMapping).where(
                    KnowledgePointMapping.knowledge_point_id == kp_id
                )
            )
            remaining = count_result.scalar() or 0

            if remaining == 0:
                # 删除孤立知识点（无子节点的）
                kp_result = await self.db.execute(
                    select(KnowledgePoint).where(KnowledgePoint.id == kp_id)
                )
                kp = kp_result.scalar_one_or_none()
                if kp and not kp.children:
                    await self.db.delete(kp)
                    points_deleted += 1
                elif kp:
                    kp.source_count = 0
                    points_decremented += 1
            else:
                kp_result = await self.db.execute(
                    select(KnowledgePoint).where(KnowledgePoint.id == kp_id)
                )
                kp = kp_result.scalar_one_or_none()
                if kp:
                    kp.source_count = remaining
                    points_decremented += 1

        await self.db.flush()
        logger.info(
            f"[KP_CLEANUP] material={material_id} "
            f"mappings_deleted={len(mappings)} points_decremented={points_decremented} "
            f"points_deleted={points_deleted}"
        )
        return {
            "mappings_deleted": len(mappings),
            "points_decremented": points_decremented,
            "points_deleted": points_deleted,
        }

    # ── 辅助方法 ────────────────────────────────────────────────

    async def _cleanup_old_mappings(self, material_id: str) -> None:
        """重复解析同一教材时，先清理旧映射"""
        nodes_result = await self.db.execute(
            select(KnowledgeNode.id).where(KnowledgeNode.material_id == material_id)
        )
        node_ids = [row[0] for row in nodes_result.all()]
        if not node_ids:
            return

        mappings_result = await self.db.execute(
            select(KnowledgePointMapping).where(
                KnowledgePointMapping.knowledge_node_id.in_(node_ids)
            )
        )
        old_mappings = mappings_result.scalars().all()

        kp_ids = set(m.knowledge_point_id for m in old_mappings)
        for m in old_mappings:
            await self.db.delete(m)

        # 递减 source_count
        for kp_id in kp_ids:
            count_result = await self.db.execute(
                select(func.count()).select_from(KnowledgePointMapping).where(
                    KnowledgePointMapping.knowledge_point_id == kp_id
                )
            )
            remaining = count_result.scalar() or 0
            kp_result = await self.db.execute(
                select(KnowledgePoint).where(KnowledgePoint.id == kp_id)
            )
            kp = kp_result.scalar_one_or_none()
            if kp:
                kp.source_count = remaining

        await self.db.flush()

    @staticmethod
    def _jaccard_similarity(text_a: str, text_b: str) -> float:
        """计算 bigram Jaccard 相似度"""
        bigrams_a = _extract_bigrams(text_a)
        bigrams_b = _extract_bigrams(text_b)
        if not bigrams_a and not bigrams_b:
            return 0.0
        intersection = sum((bigrams_a & bigrams_b).values())
        union = sum((bigrams_a | bigrams_b).values())
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _merge_keywords(kw_a: str, kw_b: str) -> str:
        """合并两个关键词字符串，去重"""
        set_a = set(k.strip() for k in kw_a.split(",") if k.strip())
        set_b = set(k.strip() for k in kw_b.split(",") if k.strip())
        merged = set_a | set_b
        return ",".join(sorted(merged))
