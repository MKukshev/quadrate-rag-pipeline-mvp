
from sentence_transformers import SentenceTransformer
from .config import EMBED_MODEL

_model = None

def get_embedder() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model

def embed(text: str):
    return get_embedder().encode(text).tolist()

def dim() -> int:
    return get_embedder().get_sentence_embedding_dimension()
