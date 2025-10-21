"""
Document Summary Storage
Separate Qdrant collection for storing document summaries
"""

import os
from datetime import datetime
from typing import Optional, List, Dict
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from . import config


SUMMARY_COLLECTION = "document_summaries"


def get_client():
    """Get Qdrant client"""
    from .qdrant_store import client
    return client()


def ensure_summary_collection():
    """
    Ensure summary collection exists
    Structure: stores document summaries with metadata
    """
    cl = get_client()
    
    collections = cl.get_collections().collections
    if any(c.name == SUMMARY_COLLECTION for c in collections):
        return
    
    print(f"[SummaryStore] Creating collection: {SUMMARY_COLLECTION}")
    
    # Создаем коллекцию с dummy vector (для совместимости с Qdrant)
    # Реально vector не используется, храним только payload
    cl.create_collection(
        collection_name=SUMMARY_COLLECTION,
        vectors_config=VectorParams(
            size=1,  # Минимальный размер
            distance=Distance.COSINE
        )
    )
    
    # Создаем индексы для быстрого поиска
    cl.create_payload_index(
        collection_name=SUMMARY_COLLECTION,
        field_name="doc_id",
        field_schema="keyword"
    )
    
    cl.create_payload_index(
        collection_name=SUMMARY_COLLECTION,
        field_name="space_id",
        field_schema="keyword"
    )
    
    print(f"[SummaryStore] Collection {SUMMARY_COLLECTION} created")


def save_document_summary(
    doc_id: str,
    space_id: str,
    summary: str,
    doc_type: Optional[str] = None,
    original_chunks: int = 0,
    summary_tokens: Optional[int] = None
) -> str:
    """
    Save document summary to separate collection
    
    Returns: summary_id (UUID)
    """
    ensure_summary_collection()
    cl = get_client()
    
    # Проверить существует ли уже summary
    existing = get_document_summary(doc_id, space_id)
    
    if summary_tokens is None:
        summary_tokens = len(summary.split())
    
    payload = {
        "doc_id": doc_id,
        "space_id": space_id,
        "doc_type": doc_type,
        "summary": summary,
        "summary_tokens": summary_tokens,
        "original_chunks": original_chunks,
        "generated_at": datetime.utcnow().isoformat(),
        "model": config.LLM_MODEL,
        "llm_mode": config.LLM_MODE,
    }
    
    if existing:
        # Обновить существующий summary
        print(f"[SummaryStore] Updating summary for {doc_id}")
        
        # Найти ID точки
        results = cl.scroll(
            collection_name=SUMMARY_COLLECTION,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
                    FieldCondition(key="space_id", match=MatchValue(value=space_id)),
                ]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False
        )
        
        if results[0]:
            point_id = results[0][0].id
            cl.set_payload(
                collection_name=SUMMARY_COLLECTION,
                payload=payload,
                points=[point_id]
            )
            return str(point_id)
    
    # Создать новый summary
    print(f"[SummaryStore] Saving new summary for {doc_id}")
    
    import uuid
    summary_id = str(uuid.uuid4())
    
    cl.upsert(
        collection_name=SUMMARY_COLLECTION,
        points=[
            PointStruct(
                id=summary_id,
                vector=[0.0],  # Dummy vector
                payload=payload
            )
        ]
    )
    
    return summary_id


def get_document_summary(doc_id: str, space_id: str) -> Optional[Dict]:
    """
    Get saved summary for a document
    
    Returns: Dict with summary info or None
    """
    try:
        ensure_summary_collection()
    except:
        return None
    
    cl = get_client()
    
    results = cl.scroll(
        collection_name=SUMMARY_COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
                FieldCondition(key="space_id", match=MatchValue(value=space_id)),
            ]
        ),
        limit=1,
        with_payload=True,
        with_vectors=False
    )
    
    if not results[0]:
        return None
    
    payload = results[0][0].payload
    
    return {
        "doc_id": payload["doc_id"],
        "space_id": payload["space_id"],
        "doc_type": payload.get("doc_type"),
        "summary": payload["summary"],
        "summary_tokens": payload.get("summary_tokens"),
        "original_chunks": payload.get("original_chunks"),
        "generated_at": payload.get("generated_at"),
        "model": payload.get("model"),
        "llm_mode": payload.get("llm_mode"),
    }


def has_document_summary(doc_id: str, space_id: str) -> bool:
    """Check if document has a saved summary"""
    return get_document_summary(doc_id, space_id) is not None


def delete_document_summary(doc_id: str, space_id: str) -> bool:
    """
    Delete summary for a document
    
    Returns: True if deleted, False if not found
    """
    try:
        ensure_summary_collection()
    except:
        return False
    
    cl = get_client()
    
    results = cl.scroll(
        collection_name=SUMMARY_COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
                FieldCondition(key="space_id", match=MatchValue(value=space_id)),
            ]
        ),
        limit=1,
        with_payload=False,
        with_vectors=False
    )
    
    if not results[0]:
        return False
    
    point_id = results[0][0].id
    
    cl.delete(
        collection_name=SUMMARY_COLLECTION,
        points_selector=[point_id]
    )
    
    print(f"[SummaryStore] Deleted summary for {doc_id}")
    return True


def list_documents_without_summary(
    space_id: str,
    doc_types: Optional[List[str]] = None,
    limit: int = 100
) -> List[str]:
    """
    Find documents that don't have summaries yet
    
    Returns: List of doc_ids
    """
    from .qdrant_store import client as get_qdrant_client
    
    cl = get_qdrant_client()
    
    # Получить все doc_id из основной коллекции
    filter_conditions = [
        FieldCondition(key="space_id", match=MatchValue(value=space_id)),
        FieldCondition(key="chunk_index", match=MatchValue(value=0)),  # Только первые чанки
    ]
    
    if doc_types:
        from qdrant_client.models import MatchAny
        filter_conditions.append(
            FieldCondition(key="doc_type", match=MatchAny(any=doc_types))
        )
    
    results = cl.scroll(
        collection_name=config.QDRANT_COLLECTION,
        scroll_filter=Filter(must=filter_conditions),
        limit=limit,
        with_payload=True,
        with_vectors=False
    )
    
    all_doc_ids = list(set([r.payload["doc_id"] for r in results[0]]))
    
    # Проверить какие из них уже имеют summary
    docs_without_summary = []
    
    for doc_id in all_doc_ids:
        if not has_document_summary(doc_id, space_id):
            docs_without_summary.append(doc_id)
    
    return docs_without_summary


def get_summary_stats(space_id: Optional[str] = None) -> Dict:
    """
    Get statistics about summaries
    
    Returns: Dict with stats
    """
    try:
        ensure_summary_collection()
    except:
        return {"error": "Summary collection not initialized"}
    
    cl = get_client()
    
    filter_conditions = []
    if space_id:
        filter_conditions.append(
            FieldCondition(key="space_id", match=MatchValue(value=space_id))
        )
    
    scroll_filter = Filter(must=filter_conditions) if filter_conditions else None
    
    results = cl.scroll(
        collection_name=SUMMARY_COLLECTION,
        scroll_filter=scroll_filter,
        limit=1000,
        with_payload=True,
        with_vectors=False
    )
    
    summaries = results[0]
    
    total = len(summaries)
    total_tokens = sum(s.payload.get("summary_tokens", 0) for s in summaries)
    
    by_space = {}
    by_type = {}
    
    for s in summaries:
        space = s.payload.get("space_id", "unknown")
        doc_type = s.payload.get("doc_type", "unknown")
        
        by_space[space] = by_space.get(space, 0) + 1
        by_type[doc_type] = by_type.get(doc_type, 0) + 1
    
    return {
        "total_summaries": total,
        "total_tokens": total_tokens,
        "average_tokens": total_tokens // total if total > 0 else 0,
        "by_space": by_space,
        "by_doc_type": by_type,
    }


def update_main_collection_summary_flag(doc_id: str, space_id: str, summary_id: str):
    """
    Update first chunk of document in main collection with summary reference
    """
    from .qdrant_store import client as get_qdrant_client
    
    cl = get_qdrant_client()
    
    # Найти первый чанк документа
    results = cl.scroll(
        collection_name=config.QDRANT_COLLECTION,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
                FieldCondition(key="space_id", match=MatchValue(value=space_id)),
                FieldCondition(key="chunk_index", match=MatchValue(value=0)),
            ]
        ),
        limit=1,
        with_payload=True,
        with_vectors=False
    )
    
    if not results[0]:
        print(f"[SummaryStore] Warning: Document {doc_id} first chunk not found")
        return
    
    point = results[0][0]
    
    # Обновить payload с флагом и ссылкой на summary
    cl.set_payload(
        collection_name=config.QDRANT_COLLECTION,
        payload={
            "has_summary": True,
            "summary_id": summary_id,
        },
        points=[point.id]
    )
    
    print(f"[SummaryStore] Updated main collection flag for {doc_id}")

