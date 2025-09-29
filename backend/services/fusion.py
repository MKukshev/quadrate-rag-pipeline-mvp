import math
from typing import Callable, Dict, List, Sequence


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    den = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    if den == 0:
        return 0.0
    return num / den


def rrf(semantic: List[Dict], keyword: List[Dict], k: int = 60, top_k: int = 8):
    ranks = {}
    for i, item in enumerate(semantic, 1):
        ranks.setdefault(item["key"], 0.0)
        ranks[item["key"]] += 1.0 / (k + i)
    for j, item in enumerate(keyword, 1):
        ranks.setdefault(item["key"], 0.0)
        ranks[item["key"]] += 1.0 / (k + j)
    payloads = {}
    for it in keyword + semantic:
        payloads.setdefault(it["key"], it["payload"])
    merged = [{"key": k_, "score": v, "payload": payloads[k_]} for k_, v in ranks.items()]
    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged[:top_k]


def mmr(
    query_vec: Sequence[float],
    candidates: List[Dict],
    top_k: int,
    lambda_mult: float,
    embed_text: Callable[[str], Sequence[float]],
) -> List[Dict]:
    if not candidates:
        return []

    unique = {}
    ordered = []
    for item in candidates:
        if item["key"] not in unique:
            unique[item["key"]] = item
            ordered.append(item)

    vectors: Dict[str, Sequence[float]] = {}

    def get_vec(item: Dict) -> Sequence[float]:
        key = item["key"]
        if key not in vectors:
            text = (item.get("payload", {}) or {}).get("text", "")
            vectors[key] = embed_text(text) if text else []
        return vectors[key]

    selected: List[Dict] = []
    query_vec = list(query_vec)
    while ordered and len(selected) < top_k:
        best_item = None
        best_score = float("-inf")
        for item in ordered:
            doc_vec = get_vec(item)
            if not doc_vec:
                continue
            sim_query = _cosine(query_vec, doc_vec)
            if selected:
                max_sim = max(_cosine(doc_vec, get_vec(sel)) for sel in selected)
            else:
                max_sim = 0.0
            score = lambda_mult * sim_query - (1 - lambda_mult) * max_sim
            if score > best_score:
                best_score = score
                best_item = item
        if best_item is None:
            break
        selected.append(best_item)
        ordered.remove(best_item)
    return selected
