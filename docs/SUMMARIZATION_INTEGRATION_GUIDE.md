# Руководство: Интеграция суммаризации в RAG-пайплайн

## 🎯 Что добавлено

### Новый модуль
📁 `backend/services/summarization.py` - сервис суммаризации

**Основные функции:**
- `summarize_text()` - простая суммаризация
- `summarize_long_text()` - map-reduce для больших текстов
- `summarize_chunks()` - суммаризация search results
- `summarize_document_by_id()` - суммаризация целого документа

---

## 🚀 Варианты интеграции

### Вариант 1: Минимальная интеграция (5 минут)

**Добавить новый endpoint для суммаризации:**

```python
# В backend/app.py добавить:

from services.summarization import summarize_document_by_id
from pydantic import BaseModel

class SummarizeRequest(BaseModel):
    doc_id: str
    space_id: str
    focus: Optional[str] = None

@app.post("/summarize")
def summarize_document(req: SummarizeRequest = Body(...)):
    """Суммаризировать документ по ID"""
    summary = summarize_document_by_id(
        doc_id=req.doc_id,
        space_id=req.space_id,
        focus=req.focus
    )
    return {"doc_id": req.doc_id, "summary": summary}
```

**Использование:**
```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "migration_plan_xyz",
    "space_id": "company_acme",
    "focus": "budget and timeline"
  }'
```

**Результат:**
```json
{
  "doc_id": "migration_plan_xyz",
  "summary": "Migration plan overview: Budget $200K, Timeline 6 months (Jan-Jun 2025), Using Kubernetes on AWS, Team of 5 engineers, Main risk: data migration complexity"
}
```

---

### Вариант 2: Автоматическая суммаризация в RAG (15 минут)

**Когда контекст слишком большой - автоматически суммаризировать:**

```python
# В backend/app.py, в функции ask():

from services.summarization import summarize_chunks

@app.post("/ask")
def ask(req: AskRequest = Body(...)):
    # ... existing search logic ...
    fused = _limit_one_chunk_per_doc(candidate_pool, effective_top_k)
    
    # NEW: Check if context is too large
    context_tokens = _count_context_tokens(fused)
    max_context = 4000  # Conservative limit
    
    if context_tokens > max_context:
        # Summarize chunks before RAG
        print(f"[RAG] Context too large ({context_tokens} tokens). Summarizing...")
        
        summary = summarize_chunks(fused, query=req.q, max_output_tokens=2000)
        
        # Use summary instead of raw chunks
        prompt = (
            "Ты — ассистент, отвечай строго по предоставленному КОНТЕКСТУ. "
            "Если данных недостаточно — так и скажи.\n\n"
            f"КОНТЕКСТ (summarized from {len(fused)} chunks):\n{summary}\n\n"
            f"ВОПРОС:\n{req.q}\n\n"
            "Ответь кратко и по делу."
        )
    else:
        # Normal RAG
        prompt = build_prompt(fused, req.q)
    
    answer = call_llm(prompt)
    # ... rest of the logic ...
```

**Эффект:**
- ✅ Автоматически обрабатывает большие контексты
- ✅ Прозрачно для пользователя
- ✅ Экономит токены

---

### Вариант 3: Режим суммаризации (30 минут)

**Добавить параметр `mode` для явного контроля:**

```python
# В backend/app.py

class AskRequest(BaseModel):
    q: str
    space_id: Optional[str] = None
    top_k: int = config.TOP_K_DEFAULT
    doc_types: Optional[List[str]] = None
    mode: str = "normal"  # NEW: "normal" | "summarize"

@app.post("/ask")
def ask(req: AskRequest = Body(...)):
    # ... search logic ...
    fused = _limit_one_chunk_per_doc(candidate_pool, effective_top_k)
    
    if req.mode == "summarize":
        # Explicit summarization mode
        summary = summarize_chunks(fused, query=req.q)
        
        prompt = f"Based on this summary:\n\n{summary}\n\nAnswer: {req.q}"
        answer = call_llm(prompt)
        
        return {
            "answer": answer,
            "summary": summary,  # Include summary in response
            "mode": "summarize",
            "sources": [...]
        }
    else:
        # Normal mode
        prompt = build_prompt(fused, req.q)
        answer = call_llm(prompt)
        return {"answer": answer, "mode": "normal", "sources": [...]}
```

**Использование:**
```bash
# Normal RAG
curl -X POST http://localhost:8000/ask \
  -d '{"q":"What are the deadlines?","space_id":"demo","mode":"normal"}'

# With summarization
curl -X POST http://localhost:8000/ask \
  -d '{"q":"What are the deadlines?","space_id":"demo","mode":"summarize"}'
```

---

### Вариант 4: Суммаризация при индексации (45 минут)

**Создавать summary чанк при загрузке документа:**

```python
# В backend/app.py, в функции ingest():

from services.summarization import summarize_text_sync

@app.post("/ingest")
async def ingest(
    space_id: str = Form(...),
    file: UploadFile = File(...),
    doc_type: Optional[str] = Form(None),
    create_summary: bool = Form(True),  # NEW: create summary by default
):
    # ... parsing logic ...
    text = _parse(file.filename, await file.read())
    chunks = split_markdown(text)
    
    # NEW: Create summary if document is large
    summary = None
    text_tokens = len(text.split())
    
    if create_summary and text_tokens > 2000:
        print(f"[Ingest] Creating summary for {file.filename} ({text_tokens} tokens)...")
        
        summary = summarize_text_sync(text, max_summary_tokens=500)
        
        # Add summary as first chunk with special marker
        summary_chunk = f"[DOCUMENT SUMMARY]\n\n{summary}\n\n[/DOCUMENT SUMMARY]"
        chunks.insert(0, summary_chunk)
    
    # Index chunks (including summary if created)
    upsert_chunks(space_id, doc_id, norm_doc_type, chunks)
    
    return {
        "doc_id": doc_id,
        "chunks_indexed": len(chunks),
        "summary": summary,
        "has_summary": summary is not None
    }
```

**Преимущества:**
- ✅ Summary всегда доступна (в индексе)
- ✅ Можно найти через поиск
- ✅ Один раз создаем, много раз используем

**Недостатки:**
- ❌ Дольше индексация
- ❌ Больше места в векторной БД

---

### Вариант 5: Email thread суммаризация (30 минут)

**Специальный endpoint для email переписки:**

```python
# В backend/app.py

@app.get("/summarize/emails")
def summarize_emails(
    space_id: str,
    topic: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
):
    """
    Summarize email correspondence
    
    Example: /summarize/emails?space_id=acme&topic=cloud migration
    """
    # Search emails
    query = topic or "all correspondence"
    results = semantic_search(
        query,
        space_id,
        doc_types=["email_correspondence"],
        top_k=100
    )
    
    if not results:
        return {"summary": "No emails found"}
    
    # Group by doc_id (email thread)
    threads = {}
    for r in results:
        doc_id = r["payload"]["doc_id"]
        if doc_id not in threads:
            threads[doc_id] = {
                "doc_id": doc_id,
                "chunks": []
            }
        threads[doc_id]["chunks"].append(r["payload"]["text"])
    
    # Summarize each thread
    thread_summaries = []
    for thread_id, thread_data in threads.items():
        thread_text = "\n\n---\n\n".join(thread_data["chunks"])
        
        summary = summarize_text_sync(
            thread_text,
            max_summary_tokens=200,
            focus=topic
        )
        
        thread_summaries.append({
            "thread_id": thread_id,
            "messages": len(thread_data["chunks"]),
            "summary": summary
        })
    
    # Overall summary
    all_text = "\n\n".join([
        f"Thread {i+1}: {s['summary']}"
        for i, s in enumerate(thread_summaries)
    ])
    
    overall = summarize_text_sync(
        all_text,
        max_summary_tokens=500,
        focus=topic
    )
    
    return {
        "topic": topic,
        "threads_analyzed": len(thread_summaries),
        "overall_summary": overall,
        "thread_summaries": thread_summaries
    }
```

**Пример использования:**
```bash
# Суммаризация всех email про "cloud migration"
curl "http://localhost:8000/summarize/emails?space_id=acme&topic=cloud%20migration"
```

**Результат:**
```json
{
  "topic": "cloud migration",
  "threads_analyzed": 5,
  "overall_summary": "Email discussions about cloud migration focused on: 1) Budget approval of $200K (March 5), 2) Technology selection: Kubernetes + AWS (March 12), 3) Timeline concerns raised by team (March 18-25), 4) Risk assessment of data migration (March 22), 5) Team formation: 5 engineers assigned (March 30)",
  "thread_summaries": [
    {
      "thread_id": "email_thread_001",
      "messages": 15,
      "summary": "Budget discussion. John proposed $200K, approved by management March 5"
    },
    ...
  ]
}
```

---

## 📊 Сравнение вариантов

| Вариант | Сложность | Время | Когда использовать |
|---------|-----------|-------|-------------------|
| **1. Новый endpoint** | ⭐ Простая | 5 мин | Базовая функциональность |
| **2. Auto в RAG** | ⭐⭐ Средняя | 15 мин | Прозрачная оптимизация |
| **3. Режим суммаризации** | ⭐⭐ Средняя | 30 мин | Контроль пользователем |
| **4. При индексации** | ⭐⭐⭐ Сложная | 45 мин | Один раз создать, много использовать |
| **5. Email threads** | ⭐⭐⭐ Сложная | 30 мин | Специфичный use case |

---

## 🎯 Рекомендуемый план интеграции

### Этап 1: Базовая суммаризация (30 минут)

```bash
# 1. Файл уже создан
# backend/services/summarization.py ✅

# 2. Добавить в app.py
```

**Добавить в `backend/app.py`:**

```python
# В начале файла
from services.summarization import (
    summarize_text_sync,
    summarize_long_text_sync,
    summarize_document_by_id,
)

# Добавить endpoint
@app.post("/summarize")
def summarize_document(
    doc_id: str = Body(...),
    space_id: str = Body(...),
    focus: Optional[str] = Body(None)
):
    """Суммаризировать документ"""
    summary = summarize_document_by_id(doc_id, space_id, focus)
    return {"doc_id": doc_id, "summary": summary}
```

**Тест:**
```bash
# После индексации документа
DOC_ID=$(curl -X POST http://localhost:8000/ingest \
  -F "file=@test.pdf" \
  -F "space_id=demo" | jq -r .doc_id)

# Суммаризировать
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d "{\"doc_id\":\"$DOC_ID\",\"space_id\":\"demo\"}"
```

---

### Этап 2: Smart context compression (15 минут)

**Автоматически суммаризировать если контекст слишком большой:**

```python
# В backend/app.py, обновить функцию ask():

from services.summarization import summarize_chunks

@app.post("/ask")
def ask(req: AskRequest = Body(...)):
    # ... existing logic до prompt building ...
    
    # NEW: Проверка размера контекста
    context_tokens = _count_context_tokens(fused)
    max_context_tokens = 4000  # Настраиваемый лимит
    
    if context_tokens > max_context_tokens:
        # Суммаризация перед RAG
        summary = summarize_chunks(fused, query=req.q, max_output_tokens=2000)
        
        prompt = (
            "Ты — ассистент, отвечай строго по предоставленному КОНТЕКСТУ.\n\n"
            f"КОНТЕКСТ (summarized from {len(fused)} chunks):\n{summary}\n\n"
            f"ВОПРОС:\n{req.q}\n\n"
            "Ответь кратко и по делу."
        )
    else:
        prompt = build_prompt(fused, req.q)
    
    answer = call_llm(prompt)
    # ... rest of logic ...
```

**Эффект:**
- Пользователь не замечает разницы
- Автоматически обрабатывает большие контексты
- Экономия токенов LLM

---

### Этап 3: Email thread summarization (30 минут)

**Специальный endpoint для ваших email:**

```python
# В backend/app.py

@app.get("/summarize/emails")
def summarize_email_threads(
    space_id: str,
    topic: Optional[str] = None
):
    """Суммаризация email переписки"""
    
    # Поиск emails
    results = semantic_search(
        topic or "all",
        space_id,
        doc_types=["email_correspondence"],
        top_k=50
    )
    
    # Group by doc_id
    threads = {}
    for r in results:
        doc_id = r["payload"]["doc_id"]
        if doc_id not in threads:
            threads[doc_id] = []
        threads[doc_id].append(r["payload"]["text"])
    
    # Summarize each thread
    summaries = []
    for doc_id, chunks in threads.items():
        thread_text = "\n\n".join(chunks)
        summary = summarize_text_sync(thread_text, max_summary_tokens=200)
        summaries.append({"thread_id": doc_id, "summary": summary})
    
    # Overall summary
    all_summaries = "\n\n".join([s["summary"] for s in summaries])
    overall = summarize_text_sync(all_summaries, max_summary_tokens=500, focus=topic)
    
    return {
        "topic": topic,
        "threads": len(summaries),
        "overall_summary": overall,
        "thread_summaries": summaries
    }
```

**Пример:**
```bash
curl "http://localhost:8000/summarize/emails?space_id=demo&topic=project%20deadlines"
```

---

## 🔧 Конфигурация

### Добавить в config.py

```python
# backend/services/config.py

# Summarization settings
SUMMARIZATION_ENABLED = os.getenv("SUMMARIZATION_ENABLED", "true").lower() == "true"
SUMMARIZATION_CHUNK_SIZE = int(os.getenv("SUMMARIZATION_CHUNK_SIZE", "8000"))
SUMMARIZATION_MAX_SUMMARY_TOKENS = int(os.getenv("SUMMARIZATION_MAX_SUMMARY_TOKENS", "500"))
SUMMARIZATION_AUTO_THRESHOLD = int(os.getenv("SUMMARIZATION_AUTO_THRESHOLD", "4000"))
```

### Добавить в .env

```bash
# Summarization
SUMMARIZATION_ENABLED=true
SUMMARIZATION_CHUNK_SIZE=8000          # Размер чанка для MAP phase
SUMMARIZATION_MAX_SUMMARY_TOKENS=500   # Макс токенов в summary
SUMMARIZATION_AUTO_THRESHOLD=4000      # Авто-суммаризация если контекст > этого
```

---

## 📝 Примеры использования

### Пример 1: Суммаризация длинного документа

```python
# Python client
import requests

# Загрузить документ
response = requests.post(
    "http://localhost:8000/ingest",
    files={"file": open("long_spec.pdf", "rb")},
    data={"space_id": "demo"}
)
doc_id = response.json()["doc_id"]

# Суммаризировать
summary_response = requests.post(
    "http://localhost:8000/summarize",
    json={
        "doc_id": doc_id,
        "space_id": "demo",
        "focus": "technical requirements"
    }
)

print(summary_response.json()["summary"])
```

### Пример 2: RAG с автоматической суммаризацией

```python
# Запрос с большим количеством релевантных документов
response = requests.post(
    "http://localhost:8000/ask",
    json={
        "q": "Tell me about all cloud migration discussions",
        "space_id": "demo",
        "top_k": 20  # Много результатов
    }
)

# Backend автоматически:
# 1. Найдет 20 чанков
# 2. Определит что контекст > 4000 tokens
# 3. Суммаризирует чанки
# 4. Ответит на основе summary

print(response.json()["answer"])
```

### Пример 3: Email thread summary

```python
# Суммаризация всех email про проект
response = requests.get(
    "http://localhost:8000/summarize/emails",
    params={
        "space_id": "demo",
        "topic": "project alpha"
    }
)

summary = response.json()
print(f"Found {summary['threads']} email threads")
print(f"\nOverall: {summary['overall_summary']}")

for thread in summary["thread_summaries"]:
    print(f"\nThread {thread['thread_id']}: {thread['summary']}")
```

---

## 🎨 UI Integration примеры

### Кнопка "Summarize" для документа

```typescript
// Frontend TypeScript
async function summarizeDocument(docId: string, spaceId: string) {
  const response = await fetch('/summarize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ doc_id: docId, space_id: spaceId })
  });
  
  const { summary } = await response.json();
  return summary;
}

// В UI
<button onClick={() => {
  const summary = await summarizeDocument(doc.id, workspace.id);
  showModal("Document Summary", summary);
}}>
  📄 Summarize
</button>
```

### Toggle для режима суммаризации

```typescript
// В chat interface
const [mode, setMode] = useState<'normal' | 'summarize'>('normal');

async function askQuestion(question: string) {
  const response = await fetch('/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      q: question,
      space_id: workspace.id,
      mode: mode  // 'normal' or 'summarize'
    })
  });
  
  return response.json();
}

// UI
<label>
  <input 
    type="checkbox" 
    checked={mode === 'summarize'}
    onChange={(e) => setMode(e.target.checked ? 'summarize' : 'normal')}
  />
  Use summarization mode (better for broad questions)
</label>
```

---

## ⚡ Performance considerations

### Время выполнения

```python
# Простая суммаризация (< 4K tokens)
Time: ~2-5 seconds
LLM calls: 1

# Map-Reduce (100K tokens, 10 chunks)
Time: ~20-50 seconds (параллельно можно ~10-15s)
LLM calls: 11 (10 MAP + 1 REDUCE)

# Email threads (5 threads)
Time: ~10-25 seconds
LLM calls: 6 (5 threads + 1 overall)
```

### Оптимизация: Параллельная обработка

```python
# В summarization.py можно добавить:

import asyncio

async def summarize_long_text_parallel(text: str, chunk_size: int = 8000) -> str:
    """Map-Reduce с параллельной MAP фазой"""
    
    chunks = split_text_by_tokens(text, max_tokens=chunk_size)
    
    # MAP PHASE: Параллельно
    async def summarize_chunk(i, chunk):
        print(f"[Worker {i}] Summarizing...")
        return await summarize_text(chunk, max_summary_tokens=300)
    
    # Запустить параллельно
    tasks = [summarize_chunk(i, chunk) for i, chunk in enumerate(chunks, 1)]
    summaries = await asyncio.gather(*tasks)
    
    # REDUCE PHASE
    combined = "\n\n".join(summaries)
    return await summarize_text(combined, max_summary_tokens=800)
```

**Ускорение:** 3-5x для больших документов

---

## 🐛 Обработка ошибок

```python
# В summarization.py

async def summarize_text(text: str, max_summary_tokens: int = 500) -> str:
    """Суммаризация с обработкой ошибок"""
    
    # Проверка пустого текста
    if not text or not text.strip():
        return "[Empty document - nothing to summarize]"
    
    # Проверка размера
    tokens = count_tokens_simple(text)
    if tokens < 50:
        return text  # Too short to summarize, return as-is
    
    try:
        prompt = f"Summarize concisely:\n\n{text}\n\nSUMMARY:"
        summary = call_llm(prompt)
        
        # Проверка результата
        if not summary or summary.startswith("[LLM"):
            return f"[Summarization failed: {summary}]"
        
        return summary.strip()
        
    except Exception as e:
        return f"[Summarization error: {str(e)}]"
```

---

## 📚 Документация API

### POST /summarize

**Request:**
```json
{
  "doc_id": "migration_plan_abc123",
  "space_id": "company_acme",
  "focus": "budget and timeline"  // optional
}
```

**Response:**
```json
{
  "doc_id": "migration_plan_abc123",
  "summary": "Cloud migration plan overview: Budget $200K, Timeline 6 months..."
}
```

### POST /ask (с суммаризацией)

**Request:**
```json
{
  "q": "What are all the cloud migration plans?",
  "space_id": "company_acme",
  "top_k": 20,
  "mode": "summarize"  // NEW: explicit summarization
}
```

**Response:**
```json
{
  "answer": "Based on the documents, there are 3 migration plans...",
  "summary": "Summary of 20 relevant chunks: ...",  // NEW
  "mode": "summarize",
  "sources": [...]
}
```

### GET /summarize/emails

**Request:**
```
GET /summarize/emails?space_id=demo&topic=project%20alpha
```

**Response:**
```json
{
  "topic": "project alpha",
  "threads_analyzed": 5,
  "overall_summary": "Email discussions covered...",
  "thread_summaries": [
    {
      "thread_id": "email_001",
      "messages": 15,
      "summary": "Budget discussion..."
    }
  ]
}
```

---

## 🎉 Готовые файлы

### 1. Сервис суммаризации
📁 `backend/services/summarization.py` ✅ Создан

**Функции:**
- `summarize_text()` - простая суммаризация
- `summarize_long_text()` - map-reduce
- `summarize_chunks()` - для search results
- `summarize_document_by_id()` - по doc_id

### 2. Примеры интеграции
📁 `backend/app_with_summarization.py` ✅ Создан

**Показывает:**
- 5 вариантов интеграции
- API endpoints
- Готовый код для копирования

### 3. Документация
📁 `docs/SUMMARIZATION_INTEGRATION_GUIDE.md` ✅ Создан

---

## 🚀 Быстрый старт

### Шаг 1: Скопировать модуль (уже готов)
```bash
# backend/services/summarization.py уже создан ✅
```

### Шаг 2: Добавить в app.py (30 строк кода)

```python
# В начале backend/app.py
from services.summarization import summarize_document_by_id

# Добавить endpoint
@app.post("/summarize")
def summarize_document(
    doc_id: str = Body(...),
    space_id: str = Body(...),
    focus: Optional[str] = Body(None)
):
    summary = summarize_document_by_id(doc_id, space_id, focus)
    return {"doc_id": doc_id, "summary": summary}
```

### Шаг 3: Тест

```bash
# 1. Индексировать документ
make ingest

# 2. Получить doc_id
curl http://localhost:8000/search?q=test&space_id=space_demo | jq '.results[0].payload.doc_id'

# 3. Суммаризировать
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"doc_id":"<DOC_ID>","space_id":"space_demo"}'
```

---

## 💡 Рекомендация

**Начните с Варианта 1 + Варианта 2:**

1. ✅ **Вариант 1** (5 мин) - базовый `/summarize` endpoint
2. ✅ **Вариант 2** (15 мин) - авто-суммаризация в `/ask` если контекст большой

**Итого:** 20 минут работы, значительное улучшение функциональности!

**Позже можно добавить:**
- Вариант 5 (email threads) - для вашей email_correspondence
- Вариант 4 (при индексации) - если нужно кэшировать summaries

Готовы начать интеграцию?

