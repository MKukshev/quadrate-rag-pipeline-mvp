# Quick Start: Ask Modes

## 🚀 TL;DR

`/ask` теперь поддерживает 4 режима работы через параметр `mode`.

---

## 📋 Режимы

| Mode | Behavior | Use When |
|------|----------|----------|
| `auto` | Smart decision (default) | Not sure |
| `normal` | Always normal RAG | Need details |
| `summarize` | Always summarize | Need brief overview |
| `detailed` | Always full details | Need ALL details |

---

## 💻 Examples

### Auto mode (default)
```bash
curl -X POST http://localhost:8000/ask \
  -d '{"q":"migration projects","space_id":"demo"}'
```

### Summarize mode (brief overview)
```bash
curl -X POST http://localhost:8000/ask \
  -d '{"q":"migration projects","space_id":"demo","mode":"summarize"}'
```

### Detailed mode (all details)
```bash
curl -X POST http://localhost:8000/ask \
  -d '{"q":"list ALL projects","space_id":"demo","mode":"detailed","top_k":50}'
```

---

## 🔍 Response

```json
{
  "answer": "...",
  "mode": "auto",           // Which mode was used
  "summarized": true,       // Was summarization applied?
  "context_tokens": 5000,   // Original context size
  "model": "llama3.1:8b"
}
```

---

## 🧪 Test

```bash
# Test all modes
make test-modes

# Or manually
curl -X POST http://localhost:8000/ask \
  -d '{"q":"test","mode":"summarize"}' | jq '.mode, .summarized'
```

---

## 📚 Learn More

- [Full Guide](docs/ASK_MODES_GUIDE.md) - Complete documentation with examples
- [LLM Model Config](docs/LLM_MODEL_CONFIGURATION.md) - How auto-mode thresholds work
- [Summarization Guide](docs/SUMMARIZATION_INTEGRATION_GUIDE.md) - Summarization patterns

---

## 🎯 Best Practices

```python
# General questions → auto
{"q": "What is X?", "mode": "auto"}

# Dashboard / Quick overview → summarize
{"q": "Overview of projects", "mode": "summarize"}

# Analytics / Reports → detailed
{"q": "List ALL projects with dates", "mode": "detailed"}
```

---

**Status:** ✅ Integrated and ready to use!

