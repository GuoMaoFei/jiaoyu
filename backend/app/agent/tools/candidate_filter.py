import re
from collections import Counter
from typing import List, Dict, Any, Optional

_CJK_PUNCT_RE = re.compile(r'[\s\u3000-\u303f\uff00-\uffef\u2000-\u206f]')

_TREE_PROXIMITY_WEIGHTS = {
    "self": 0.30,
    "sibling": 0.20,
    "parent": 0.15,
    "grandparent": 0.10,
    "distant": 0.0,
}

# 知识点维度的树近邻权重（更重视兄弟和子节点关系）
_KP_TREE_PROXIMITY_WEIGHTS = {
    "self": 0.25,
    "sibling": 0.15,
    "parent": 0.10,
    "grandparent": 0.05,
    "child": 0.15,
    "distant": 0.0,
}


def _extract_bigrams(text: str) -> Counter:
    cleaned = _CJK_PUNCT_RE.sub('', text.lower())
    if len(cleaned) < 2:
        return Counter()
    return Counter(cleaned[i:i+2] for i in range(len(cleaned) - 1))


def _tree_proximity(
    candidate_kn_id: str,
    candidate_parent_id: Optional[str],
    current_node_id: Optional[str],
    nodes_map: Optional[Dict[str, Any]],
) -> float:
    if not current_node_id or not nodes_map or current_node_id not in nodes_map:
        return 0.0

    current = nodes_map[current_node_id]
    current_parent = str(current.parent_id) if current.parent_id else None
    current_gp = None
    if current_parent and current_parent in nodes_map:
        current_gp = str(nodes_map[current_parent].parent_id) if nodes_map[current_parent].parent_id else None

    if candidate_kn_id == current_node_id:
        return _TREE_PROXIMITY_WEIGHTS["self"]
    if candidate_parent_id and candidate_parent_id == current_parent and current_parent:
        return _TREE_PROXIMITY_WEIGHTS["sibling"]
    if candidate_kn_id == current_parent:
        return _TREE_PROXIMITY_WEIGHTS["parent"]
    if current_gp and candidate_kn_id == current_gp:
        return _TREE_PROXIMITY_WEIGHTS["grandparent"]
    candidate_gp = None
    if candidate_parent_id and candidate_parent_id in nodes_map:
        cp = nodes_map[candidate_parent_id]
        candidate_gp = str(cp.parent_id) if cp.parent_id else None
    if current_gp and candidate_gp and current_gp == candidate_gp:
        return _TREE_PROXIMITY_WEIGHTS["grandparent"]
    return _TREE_PROXIMITY_WEIGHTS["distant"]


def rank_candidates(
    query: str,
    pool: List[Dict[str, Any]],
    top_k: int = 3,
    current_node_id: Optional[str] = None,
    nodes_map: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if not pool:
        return []
    if not query.strip():
        return pool[:top_k]

    query_bigrams = _extract_bigrams(query)
    query_len = sum(query_bigrams.values()) if query_bigrams else 1

    scored = []
    for candidate in pool:
        searchable = candidate.get("title", "") + candidate.get("summary", "")
        cand_bigrams = _extract_bigrams(searchable)
        overlap = sum((query_bigrams & cand_bigrams).values())
        text_score = overlap / query_len if query_len > 0 else 0.0

        tree_score = _tree_proximity(
            candidate.get("knowledge_node_id"),
            candidate.get("parent_id"),
            current_node_id,
            nodes_map,
        )

        scored.append((text_score + tree_score, candidate))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


def prefilter_candidates(
    query: str,
    pool: List[Dict[str, Any]],
    top_k: int = 12,
) -> List[Dict[str, Any]]:
    if not pool:
        return []
    if not query.strip():
        return pool[:top_k]

    query_bigrams = _extract_bigrams(query)
    if not query_bigrams:
        return pool[:top_k]

    query_len = sum(query_bigrams.values())

    scored = []
    for candidate in pool:
        searchable = candidate.get("title", "") + candidate.get("summary", "")
        cand_bigrams = _extract_bigrams(searchable)
        overlap = sum((query_bigrams & cand_bigrams).values())
        score = overlap / query_len if query_len > 0 else 0.0
        scored.append((score, candidate))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]
