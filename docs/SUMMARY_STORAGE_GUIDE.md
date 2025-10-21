# Руководство: Summary Storage (Pattern 4)

## 🎯 Концепция

Pre-compute document summaries at index time and store them in separate Qdrant collection. Enables instant summary retrieval instead of generating on every request.

---

## 🏗 Архитектура

### Две коллекции в Qdrant

#### 1. `rag_embeddings` (основная)
```python
{
  "doc_id": "doc_123",
  "space_id": "demo",
  "chunk_index": 0,
  "text": "...",
  "doc_type": "technical_docs",
  "has_summary": true,        # NEW: Флаг наличия summary
  "summary_id": "uuid-456"    # NEW: Ссылка на summary
}
```

#### 2. `document_summaries` (новая)
```python
{
  "doc_id": "doc_123",
  "space_id": "demo",
  "doc_type": "technical_docs",
  "summary": "Full summary text...",
  "summary_tokens": 150,
  "original_chunks": 25,
  "generated_at": "2025-10-21T10:30:00Z",
  "model": "llama3.1:8b",
  "llm_mode": "ollama"
}
```

---

## 🔄 Workflow

### A. Индексация с суммаризацией

```
POST /ingest (generate_summary=true)
       │
       ├─→ 1. Parse document
       ├─→ 2. Split into chunks
       ├─→ 3. Generate embeddings
       ├─→ 4. Save to rag_embeddings
       ├─→ 5. Return response (3s)
       │
       └─→ 6. Background Task:
              ├─→ Generate summary (15s)
              ├─→ Save to document_summaries
              └─→ Update rag_embeddings flag
```

**Ключевое:** Пользователь не ждёт суммаризацию!

### B. Получение summary

```
POST /summarize
       │
       ├─→ 1. Check document_summaries
       │      │
       │      ├─→ Found? → Return (0.1s) ✅
       │      │
       │      └─→ Not found? → Generate on-the-fly (15s)
       │
       └─→ 2. Return summary
```

**Ключевое:** Кэширование из отдельной коллекции!

---

## 📝 API Reference

### 1. Ingest with Summary

**Request:**
```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@document.pdf" \
  -F "space_id=demo" \
  -F "doc_type=technical_docs" \
  -F "generate_summary=true"
```

**Response:**
```json
{
  "doc_id": "document_abc123",
  "space_id": "demo",
  "doc_type": "technical_docs",
  "chunks_indexed": 25,
  "summary_pending": true
}
```

**Время:** ~3 секунды (summary генерируется в фоне)

---

### 2. Check Summary Status

**Request:**
```bash
GET /documents/{doc_id}/summary-status?space_id=demo
```

**Response (есть summary):**
```json
{
  "doc_id": "doc_123",
  "space_id": "demo",
  "has_summary": true,
  "summary_preview": "This document discusses cloud migration strategies including...",
  "summary_tokens": 150,
  "generated_at": "2025-10-21T10:30:00Z",
  "model": "llama3.1:8b"
}
```

**Response (нет summary):**
```json
{
  "doc_id": "doc_123",
  "space_id": "demo",
  "has_summary": false
}
```

---

### 3. Get Summary (with Caching)

**Request:**
```bash
POST /summarize
{
  "doc_id": "doc_123",
  "space_id": "demo",
  "focus": null
}
```

**Response (cached):**
```json
{
  "doc_id": "doc_123",
  "space_id": "demo",
  "summary": "Full summary text...",
  "chunks_processed": 25,
  "focus": null,
  "cached": true,
  "generated_at": "2025-10-21T10:30:00Z"
}
```

**Response (on-the-fly):**
```json
{
  "doc_id": "doc_123",
  "space_id": "demo",
  "summary": "Full summary text...",
  "chunks_processed": 25,
  "focus": null,
  "cached": false
}
```

**Важно:** Если есть `focus` - всегда генерирует заново (т.к. focus меняет результат)

---

### 4. Bulk Summarization

**Request:**
```bash
POST /bulk-summarize?space_id=demo&doc_types=technical_docs&limit=100
```

**Response:**
```json
{
  "space_id": "demo",
  "documents_to_process": 15,
  "doc_ids": ["doc_1", "doc_2", ...],
  "status": "scheduled"
}
```

**Use case:** Суммаризация всех существующих документов которые не имеют summary

---

### 5. Regenerate Summary

**Request:**
```bash
POST /documents/{doc_id}/regenerate-summary?space_id=demo
```

**Response (async):**
```json
{
  "doc_id": "doc_123",
  "space_id": "demo",
  "status": "pending",
  "message": "Summary regeneration scheduled"
}
```

**Use case:** Обновить summary после смены модели LLM

---

### 6. Summary Statistics

**Request:**
```bash
GET /summary-stats?space_id=demo
```

**Response:**
```json
{
  "total_summaries": 45,
  "total_tokens": 6750,
  "average_tokens": 150,
  "by_space": {
    "demo": 30,
    "production": 15
  },
  "by_doc_type": {
    "technical_docs": 20,
    "protocols": 15,
    "presentations": 10
  }
}
```

---

### 7. Delete Summary

**Request:**
```bash
DELETE /documents/{doc_id}/summary?space_id=demo
```

**Response:**
```json
{
  "doc_id": "doc_123",
  "space_id": "demo",
  "status": "deleted"
}
```

---

## 🔧 Implementation Details

### Backend Module: `summary_store.py`

```python
# Основные функции
save_document_summary(doc_id, space_id, summary, ...)
get_document_summary(doc_id, space_id) → Dict | None
has_document_summary(doc_id, space_id) → bool
delete_document_summary(doc_id, space_id) → bool
list_documents_without_summary(space_id, ...) → List[str]
get_summary_stats(space_id) → Dict
update_main_collection_summary_flag(doc_id, space_id, summary_id)
```

### Background Task

```python
def _generate_and_save_summary_task(doc_id, space_id, doc_type, num_chunks):
    """
    Асинхронная генерация и сохранение summary
    
    1. Генерирует summary через summarize_document_by_id()
    2. Сохраняет в document_summaries
    3. Обновляет флаг в rag_embeddings
    """
```

---

## 📊 Performance Comparison

| Operation | Without Storage | With Storage | Improvement |
|-----------|----------------|--------------|-------------|
| **First /summarize** | 15s | 15s | - |
| **Second /summarize** | 15s | 0.1s | **150x faster** |
| **Dashboard (10 docs)** | 150s | 1s | **150x faster** |
| **Ingest time** | 3s | 3s | No impact |

---

## 🎯 Use Cases

### 1. Document Library UI

```typescript
// Load documents with previews
async function loadDocuments() {
  const docs = await fetchDocumentsList();
  
  // Check which have summaries (parallel)
  const statusChecks = await Promise.all(
    docs.map(doc => 
      fetch(`/documents/${doc.id}/summary-status?space_id=${workspace}`)
    )
  );
  
  // Show preview for documents with summaries
  return docs.map((doc, i) => ({
    ...doc,
    hasSummary: statusChecks[i].has_summary,
    preview: statusChecks[i].summary_preview
  }));
}
// ✅ Fast preview without full summarization
```

### 2. Dashboard Overview

```typescript
// Show summary cards for all projects
async function loadProjectSummaries(projectIds: string[]) {
  const summaries = await Promise.all(
    projectIds.map(id => 
      fetch('/summarize', {
        body: JSON.stringify({doc_id: id, space_id: workspace})
      })
    )
  );
  
  return summaries.map(s => ({
    project: s.doc_id,
    summary: s.summary,
    cached: s.cached  // All should be true!
  }));
}
// ✅ Instant load from cache
```

### 3. Batch Upload Flow

```typescript
// Upload multiple documents
async function batchUpload(files: File[]) {
  // 1. Upload all files
  for (const file of files) {
    await uploadFile(file, {generate_summary: true});
  }
  
  // 2. Show "Processing summaries..." message
  showNotification("Documents indexed. Summaries generating in background...");
  
  // 3. Poll for completion
  setTimeout(checkAllSummariesReady, 30000);
}

async function checkAllSummariesReady() {
  const stats = await fetch('/summary-stats?space_id=' + workspace);
  
  if (stats.total_summaries >= expectedCount) {
    showNotification("All summaries ready!");
    refreshDocumentList();
  }
}
// ✅ Non-blocking upload + background processing
```

### 4. Model Migration

```typescript
// After switching LLM model, regenerate all summaries
async function regenerateAllSummaries() {
  // Bulk regeneration
  const response = await fetch('/bulk-summarize?space_id=' + workspace);
  
  showNotification(`Regenerating ${response.documents_to_process} summaries with new model...`);
  
  // Poll progress
  const interval = setInterval(async () => {
    const stats = await fetch('/summary-stats');
    updateProgress(stats);
  }, 5000);
}
// ✅ Easy model updates
```

---

## 🔍 Debugging

### Check if summary exists

```bash
curl "http://localhost:8000/documents/doc_123/summary-status?space_id=demo"
```

### View all summaries in space

```bash
curl "http://localhost:8000/summary-stats?space_id=demo" | jq
```

### Find documents without summaries

```bash
# Trigger bulk to see which need processing
curl -X POST "http://localhost:8000/bulk-summarize?space_id=demo&limit=10" | jq '.doc_ids'
```

### Check backend logs

```bash
make logs

# Look for:
# [Ingest] Scheduling background summarization for doc_123
# [Background] Starting summarization for doc_123
# [Background] Summary saved for doc_123, id=uuid-456
# [Summarize] Using cached summary for doc_123
```

---

## ⚙️ Configuration

### Enable by default (optional)

```python
# In backend/app.py, change default:
generate_summary: bool = Form(True)  # Instead of False
```

### Async vs Sync

```python
# Current: Async (recommended)
background_tasks.add_task(generate_summary_task, ...)

# Alternative: Sync (blocks ingest)
summary = summarize_document_by_id(...)
save_document_summary(...)
```

---

## 🎉 Summary

**What we built:**
- ✅ Separate Qdrant collection for summaries
- ✅ Async background generation
- ✅ Smart caching in `/summarize`
- ✅ Bulk operations
- ✅ Summary status API
- ✅ Statistics and management

**Benefits:**
- 🚀 150x faster repeated summary requests
- 🚀 Non-blocking document ingestion
- 🚀 Dashboard-friendly (instant previews)
- 🚀 Easy model updates (regeneration)

**Ready to use!** 🎊

