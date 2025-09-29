
import shutil
from pathlib import Path
from typing import List, Optional
from whoosh import index
from whoosh.fields import Schema, TEXT, ID, NUMERIC
from whoosh.qparser import MultifieldParser, OrGroup
from whoosh.query import Term, Or, And
from whoosh import scoring
from .config import KEYWORD_INDEX_DIR

_schema = Schema(
    uid=ID(stored=True, unique=True),
    doc_id=ID(stored=True),
    space_id=ID(stored=True),
    doc_type=ID(stored=True),
    chunk_index=NUMERIC(stored=True),
    text=TEXT(stored=True)
)

_ix = None

def _ensure_index():
    global _ix
    if _ix is not None:
        return _ix
    KEYWORD_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if index.exists_in(KEYWORD_INDEX_DIR):
            existing = index.open_dir(KEYWORD_INDEX_DIR)
            stored_fields = set(existing.schema.names())
            if "doc_type" not in stored_fields:
                existing.close()
                shutil.rmtree(KEYWORD_INDEX_DIR)
                KEYWORD_INDEX_DIR.mkdir(parents=True, exist_ok=True)
                raise FileNotFoundError
            _ix = existing
        else:
            raise FileNotFoundError
    except FileNotFoundError:
        _ix = index.create_in(KEYWORD_INDEX_DIR, schema=_schema)
    return _ix

def add_chunks(space_id: str, doc_id: str, doc_type: str, chunks: List[str]):
    ix = _ensure_index()
    writer = ix.writer()
    for i, text in enumerate(chunks):
        uid = f"{doc_id}:{i}"
        writer.update_document(uid=uid, doc_id=doc_id, space_id=space_id,
                               doc_type=doc_type, chunk_index=i, text=text)
    writer.commit()

def search(q: str, space_id: Optional[str], doc_types: Optional[List[str]], top_k: int = 8):
    ix = _ensure_index()
    qp = MultifieldParser(["text"], schema=_schema, group=OrGroup)
    query = qp.parse(q)
    weight = scoring.BM25F()
    with ix.searcher(weighting=weight) as s:
        filt = None
        filters = []
        if space_id:
            filters.append(Term("space_id", space_id))
        if doc_types:
            filters.append(Or([Term("doc_type", dt) for dt in doc_types]))
        if filters:
            filt = filters[0] if len(filters) == 1 else And(filters)
        results = s.search(query, limit=top_k, filter=filt)
        out = []
        for r in results:
            out.append({
                "key": r["uid"],
                "score": float(r.score),
                "payload": {
                    "doc_id": r["doc_id"],
                    "space_id": r["space_id"],
                    "doc_type": r.get("doc_type"),
                    "chunk_index": int(r["chunk_index"]),
                    "text": r["text"]
                }
            })
        return out
