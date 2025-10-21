## Quick Start: Summary Storage (Pattern 4)

## 🚀 TL;DR

Documents can now have pre-computed summaries stored in separate Qdrant collection. Summaries are generated asynchronously during ingestion or on-demand.

---

## 📋 Key Features

1. **Async generation** - summaries created in background, doesn't block ingestion
2. **Separate storage** - dedicated Qdrant collection for summaries
3. **Smart caching** - `/summarize` checks for cached summary first
4. **Bulk operations** - process multiple documents at once
5. **Regeneration** - update summaries when model changes

---

## 💻 Quick Examples

### 1. Ingest with Summary
```bash
# Upload document with automatic summary generation
curl -X POST http://localhost:8000/ingest \
  -F "file=@document.pdf" \
  -F "space_id=demo" \
  -F "generate_summary=true"

# Response:
# {
#   "doc_id": "document_abc123",
#   "chunks_indexed": 25,
#   "summary_pending": true  ← Generated in background
# }
```

### 2. Check Summary Status
```bash
curl "http://localhost:8000/documents/document_abc123/summary-status?space_id=demo"

# Response:
# {
#   "has_summary": true,
#   "summary_preview": "This document discusses...",
#   "summary_tokens": 150
# }
```

### 3. Get Cached Summary
```bash
curl -X POST http://localhost:8000/summarize \
  -d '{"doc_id":"document_abc123","space_id":"demo"}'

# Response:
# {
#   "summary": "Full summary text...",
#   "cached": true  ← Instant response!
# }
```

### 4. Bulk Summarize
```bash
# Summarize all documents without summaries
curl -X POST "http://localhost:8000/bulk-summarize?space_id=demo&limit=50"

# Response:
# {
#   "documents_to_process": 15,
#   "status": "scheduled"
# }
```

---

## 🔍 Architecture

### Separate Collection
```
Qdrant Collections:
├── rag_embeddings (main)      - Document chunks + embeddings
│   └── payload:
│       ├── has_summary: true
│       └── summary_id: "uuid"
│
└── document_summaries (new)    - Pre-computed summaries
    └── payload:
        ├── doc_id
        ├── summary (full text)
        ├── summary_tokens
        ├── generated_at
        └── model
```

### Flow
```
POST /ingest + generate_summary=true
  ↓
1. Index chunks → Qdrant (3s)
2. Return response immediately
3. Background: Generate summary (15s)
4. Save to document_summaries collection
5. Update main collection flag

Later...
POST /summarize
  ↓
1. Check document_summaries (0.1s)
2. If found → return cached
3. If not → generate on-the-fly
```

---

## 📊 Benefits

| Feature | Before | After |
|---------|--------|-------|
| **Ingest time** | 3s | 3s (summary in background) |
| **Summary retrieval** | 15s (generate) | 0.1s (cached) |
| **Repeated requests** | 15s each | 0.1s (instant) |
| **Storage** | N/A | Separate collection |

---

## 🧪 Test

```bash
# Run all tests
make test-summary-store

# Manual test
curl -X POST http://localhost:8000/ingest \
  -F "file=@docs/notes_meeting.txt" \
  -F "space_id=demo" \
  -F "generate_summary=true"

# Wait 10 seconds, then check
curl "http://localhost:8000/summary-stats?space_id=demo" | jq
```

---

## 📚 All Endpoints

```bash
# During ingest
POST /ingest?generate_summary=true

# Check status
GET /documents/{doc_id}/summary-status?space_id=demo

# Get summary (with caching)
POST /summarize

# Bulk operations
POST /bulk-summarize?space_id=demo&limit=100

# Regenerate
POST /documents/{doc_id}/regenerate-summary?space_id=demo

# Statistics
GET /summary-stats?space_id=demo

# Delete
DELETE /documents/{doc_id}/summary?space_id=demo
```

---

## 🎯 Use Cases

**1. Dashboard Overview**
```typescript
// Load all document summaries instantly
const summaries = await Promise.all(
  docIds.map(id => fetch(`/summarize`, {body: {doc_id: id}}))
);
// ✅ Instant response from cache
```

**2. Document Library**
```typescript
// Show preview on hover
const preview = await fetch(`/documents/${docId}/summary-status`);
// ✅ Quick preview without full summarization
```

**3. Batch Processing**
```typescript
// After uploading many documents
await fetch(`/bulk-summarize?space_id=${workspace}`);
// ✅ All summaries generated in background
```

---

**Status:** ✅ Integrated and ready to use!

**Learn more:** [Full Pattern 4 Documentation](docs/SUMMARY_STORAGE_GUIDE.md)

