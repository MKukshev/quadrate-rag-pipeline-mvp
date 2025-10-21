# Quick Start: Streaming Summarization (Pattern 5)

## 🚀 TL;DR

Real-time progressive summarization with Server-Sent Events (SSE). Users see progress, partial results, and ETA instead of waiting blindly.

---

## 📋 Key Features

1. **Real-time progress** - see % completion and current stage
2. **Partial results** - view summaries as they're generated
3. **ETA calculation** - estimated time remaining
4. **Instant for cached** - returns immediately if summary exists
5. **Cancellable** - abort long-running summarizations

---

## 💻 Quick Examples

### 1. SSE Streaming (Recommended)

```bash
# Stream summarization with progress
curl -X POST http://localhost:8000/summarize-stream \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "document_abc123",
    "space_id": "demo"
  }' \
  --no-buffer

# Output (Server-Sent Events):
# data: {"type":"start","total_tokens":15000,"strategy":"map_reduce","progress":0}
#
# data: {"type":"processing","progress":5,"message":"Large document...","eta_seconds":45}
#
# data: {"type":"progress","stage":"map","current":1,"total":3,"progress":30,"eta_seconds":30}
#
# data: {"type":"partial_summary","chunk":1,"summary":"Section 1 discusses...","tokens":150}
#
# data: {"type":"progress","stage":"reduce","progress":75,"message":"Combining summaries..."}
#
# data: {"type":"summary","text":"Final comprehensive summary...","progress":100}
#
# data: {"type":"complete","total_time":42.5}
```

### 2. HTML Demo

```bash
# Open visual demo in browser
open http://localhost:8000/static/streaming_demo.html

# Or open local file
open static/streaming_demo.html
```

### 3. JavaScript Client

```javascript
// Frontend integration
async function streamingSummarize(docId, spaceId) {
  const response = await fetch('/summarize-stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ doc_id: docId, space_id: spaceId })
  });
  
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n').filter(l => l.startsWith('data: '));
    
    for (const line of lines) {
      const event = JSON.parse(line.substring(6));
      
      // Update UI based on event type
      switch (event.type) {
        case 'progress':
          updateProgressBar(event.progress);
          updateStatus(event.message, event.eta_seconds);
          break;
        
        case 'partial_summary':
          addPartialResult(event.chunk, event.summary);
          break;
        
        case 'summary':
          showFinalSummary(event.text);
          break;
      }
    }
  }
}
```

---

## 📊 Event Types

| Type | Description | Fields |
|------|-------------|--------|
| `cached` | Summary loaded from cache | `summary`, `progress`: 100 |
| `start` | Process started | `total_tokens`, `strategy`, `map_chunks` |
| `processing` | Processing stage | `message`, `progress`, `eta_seconds` |
| `progress` | Map/Reduce progress | `stage`, `current`, `total`, `eta_seconds` |
| `partial_summary` | Chunk completed | `chunk`, `summary`, `tokens` |
| `summary` | Final result | `text`, `tokens`, `processing_time` |
| `complete` | Finished | `total_time`, `tokens_processed` |
| `error` | Error occurred | `message` |

---

## 🎯 Comparison

| Feature | `/summarize` | `/summarize-stream` |
|---------|--------------|---------------------|
| **Wait time** | Full 15-60s | See progress |
| **User feedback** | None | Real-time |
| **ETA** | No | Yes |
| **Partial results** | No | Yes |
| **Cancellable** | No | Yes |
| **Use for** | Small docs | Large docs (100+ pages) |

---

## 🧪 Test

```bash
# Run all streaming tests
make test-streaming

# Manual test with curl
curl -X POST http://localhost:8000/summarize-stream \
  -d '{"doc_id":"doc_123","space_id":"demo"}' \
  --no-buffer

# Visual demo
open static/streaming_demo.html
```

---

## 🎨 UI Components

### Progress Bar
```typescript
<div className="progress-bar">
  <div style={{ width: `${progress}%` }}>
    {progress}%
  </div>
</div>
```

### Status with ETA
```typescript
<div className="status">
  {message}
  {eta && ` (${eta}s remaining)`}
</div>
```

### Partial Results
```typescript
{partialResults.map((result, i) => (
  <div key={i} className="chunk">
    <strong>Chunk {result.chunk}:</strong>
    <p>{result.summary}</p>
  </div>
))}
```

---

## 📚 When to Use

**Use `/summarize-stream` for:**
- ✅ Large documents (100+ pages, 15K+ tokens)
- ✅ Multi-document summaries
- ✅ Interactive dashboards
- ✅ User-facing applications
- ✅ When progress feedback is important

**Use regular `/summarize` for:**
- ✅ Small documents (<10 pages)
- ✅ Background jobs
- ✅ API integrations
- ✅ When caching is sufficient

---

**Status:** ✅ Integrated and ready to use!

**Learn more:** [Full Streaming Guide](docs/STREAMING_SUMMARIZATION_GUIDE.md)

