
import uuid
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    HnswConfigDiff,
    SearchParams,
)
from . import config
from .config import QDRANT_URL, QDRANT_COLLECTION
from .embeddings import embed, dim

_client: Optional[QdrantClient] = None

def client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL)
        ensure_collection()
    return _client

def ensure_collection():
    c = QdrantClient(url=QDRANT_URL)
    try:
        c.get_collection(QDRANT_COLLECTION)
    except Exception:
        c.recreate_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=dim(), distance=Distance.COSINE),
            hnsw_config=HnswConfigDiff(m=config.QDRANT_HNSW_M, ef_construct=config.QDRANT_HNSW_EF_CONSTRUCT),
        )
    else:
        try:
            c.update_collection(
                collection_name=QDRANT_COLLECTION,
                hnsw_config=HnswConfigDiff(m=config.QDRANT_HNSW_M, ef_construct=config.QDRANT_HNSW_EF_CONSTRUCT),
            )
        except Exception:
            pass

def upsert_chunks(space_id: str, doc_id: str, doc_type: str, chunks: List[str]):
    points = []
    for idx, text in enumerate(chunks):
        vec = embed(text)
        payload = {
            "doc_id": doc_id,
            "space_id": space_id,
            "doc_type": doc_type,
            "chunk_index": idx,
            "text": text
        }
        points.append(PointStruct(id=str(uuid.uuid4()), vector=vec, payload=payload))
    if points:
        client().upsert(collection_name=QDRANT_COLLECTION, points=points)

def delete_by_doc(doc_id: str):
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    client().delete(QDRANT_COLLECTION, points_selector=Filter(
        must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
    ))

def semantic_search(q: str, space_id: Optional[str], doc_types: Optional[List[str]], top_k: int = 8):
    qv = embed(q)
    flt = None
    must = []
    if space_id:
        must.append(FieldCondition(key="space_id", match=MatchValue(value=space_id)))
    if doc_types:
        must.append(FieldCondition(key="doc_type", match=MatchAny(any=doc_types)))
    if must:
        flt = Filter(must=must)
    hits = client().search(
        collection_name=QDRANT_COLLECTION,
        query_vector=qv,
        query_filter=flt,
        limit=top_k,
        search_params=SearchParams(hnsw_ef=config.QDRANT_HNSW_EF_SEARCH),
    )
    return [{"key": f"{h.payload.get('doc_id')}:{h.payload.get('chunk_index')}",
             "score": float(h.score),
             "payload": h.payload} for h in hits]
