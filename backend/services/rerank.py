from typing import Dict, List

from . import config
from .context import compress_text

_model = None


def _get_reranker():
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder

        device = None  # auto
        _model = CrossEncoder(config.RERANK_MODEL, device=device)
    return _model


def _predict_scores(query: str, texts: List[str]) -> List[float]:
    if not texts:
        return []
    model = _get_reranker()
    pairs = [(query, text) for text in texts]
    return model.predict(pairs, batch_size=config.RERANK_BATCH_SIZE).tolist()


_predict_scores_original = _predict_scores


def apply_rerank(query: str, candidates: List[Dict]) -> List[Dict]:
    if not config.RERANK_ENABLED:
        return candidates
    valid = [c for c in candidates if (c.get("payload") or {}).get("text")]
    if not valid:
        return candidates
    top_n = min(len(valid), config.RERANK_MAX_CANDIDATES)
    subset = valid[:top_n]
    texts = [compress_text(c["payload"]["text"], query) for c in subset]
    try:
        scores = _predict_scores(query, texts)
    except Exception:
        return candidates
    scored = list(zip(subset, scores))
    scored.sort(key=lambda item: item[1], reverse=True)
    ordered = [item[0] for item in scored]
    seen_keys = {item.get("key") for item in ordered}
    ordered.extend([c for c in candidates if c.get("key") not in seen_keys])
    return ordered
