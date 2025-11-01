# Детальное логирование времени (Timing Breakdown)

## ✅ Что добавлено

Полная трассировка времени от HTTP запроса до ответа:

1. ⏰ **HTTP Request** - время поступления запроса
2. ⏰ **LLM Send** - время отправки в LLM
3. ⏰ **LLM Receive** - время получения ответа от LLM
4. ⏰ **HTTP Response** - время отправки ответа клиенту

---

## 🔧 Реализация

### 1. HTTP Middleware (app.py)

Логирует время для ВСЕХ endpoints:

```python
class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_time = datetime.now()
        start_time = time.time()
        
        # Логирование входящего запроса
        print(f"[HTTP REQUEST ⬇️ ] {request.method} {request.url.path}")
        print(f"  ⏰ Request time: {request_time.strftime('%H:%M:%S.%f')}")
        
        # Вызов endpoint
        response = await call_next(request)
        
        # Логирование ответа
        elapsed = time.time() - start_time
        print(f"[HTTP RESPONSE ⬆️ ] {request.method} {request.url.path}")
        print(f"  ⏱️  Total HTTP time: {elapsed:.3f}s")
        
        return response
```

### 2. LLM Timing (rag.py)

Логирует время внутри `call_llm()`:

```python
def call_llm(prompt: str, max_tokens: int = None) -> str:
    request_start = datetime.now()
    start_time = time.time()
    
    # Логирование запроса
    print(f"🚀 Sending request to Ollama...")
    llm_send_time = datetime.now()
    print(f"  ⏰ LLM send time: {llm_send_time}")
    
    # Вызов LLM
    response = requests.post(...)
    
    # Логирование ответа
    llm_receive_time = datetime.now()
    print(f"✅ Response received from Ollama!")
    print(f"  ⏰ LLM receive time: {llm_receive_time}")
    
    # Breakdown
    print(f"⏱️  TIMING BREAKDOWN:")
    print(f"  - Request start:  {request_start}")
    print(f"  - LLM send:       {llm_send_time}")
    print(f"  - LLM receive:    {llm_receive_time}")
    print(f"  - Total:          {elapsed:.3f}s")
```

---

## 📊 Формат логов

### Полная цепочка для `/summarize`:

```
🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 
[HTTP REQUEST ⬇️ ] POST /summarize
  ⏰ Request time: 20:15:30.123
  📍 Client: 192.168.65.1
────────────────────────────────────────────────────────────────────────────────

[Summarize] Generating on-the-fly summary for test_doc_564945be
[Language Detection] Input text language: ru (Русский)
[Summarization] Dynamic max_tokens: 500 (requested: 500, available: 4096)

================================================================================
[LLM REQUEST → Ollama] Model: llama3.1:8b
================================================================================
📝 INPUT:
  - Prompt length: 973 chars, ~152 tokens
  - Max output tokens: 500
  - Context window: 40960
  - Timeout: 300s
  ⏰ Request time: 20:15:30.145
────────────────────────────────────────────────────────────────────────────────
PROMPT PREVIEW (first 500 chars):
ВАЖНО: Отвечай на РУССКОМ ЯЗЫКЕ...
================================================================================
🚀 Sending request to Ollama...
  ⏰ LLM send time: 20:15:30.156

... [генерация 26 секунд] ...

✅ Response received from Ollama!
  ⏰ LLM receive time: 20:15:56.234

================================================================================
[LLM RESPONSE ← Ollama]
================================================================================
📤 OUTPUT:
  - Response length: 1234 chars, ~156 tokens
  - Generation time: 26.08s
  - Speed: ~6.0 tokens/sec
────────────────────────────────────────────────────────────────────────────────
⏱️  TIMING BREAKDOWN:
  - Request start:  20:15:30.145
  - LLM send:       20:15:30.156
  - LLM receive:    20:15:56.234
  - Total:          26.089s
────────────────────────────────────────────────────────────────────────────────
RESPONSE PREVIEW (first 500 chars):
Проект Alpha был запущен...
================================================================================

────────────────────────────────────────────────────────────────────────────────
[HTTP RESPONSE ⬆️ ] POST /summarize
  ✅ Status: 200
  ⏱️  Total HTTP time: 26.234s
  ⏰ Response time: 20:15:56.357
🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 🌐 
```

---

## ⏱️ Временные метки

### Что измеряется:

```
HTTP Request received       20:15:30.123  ← Время поступления в endpoint
  │
  ├─ Processing (app.py)     ~0.02s
  │
  ├─ LLM send                20:15:30.156  ← Отправка в Ollama/vLLM
  │
  ├─ LLM generation          ~26.08s       ← Генерация ответа
  │
  ├─ LLM receive             20:15:56.234  ← Получение ответа
  │
  ├─ Post-processing         ~0.12s
  │
HTTP Response sent          20:15:56.357  ← Отправка клиенту

Total: 26.234s
```

---

## 📊 Breakdown по компонентам

### Для суммаризации (`/summarize`):

```
Total HTTP time:     26.234s (100%)
├─ Pre-LLM:          0.020s  (0.1%)   - Загрузка данных, подготовка
├─ LLM generation:   26.089s (99.5%)  - Генерация LLM
└─ Post-LLM:         0.125s  (0.4%)   - Обработка результата
```

### Для RAG (`/ask`):

```
Total HTTP time:     3.456s (100%)
├─ Search:           0.234s  (6.8%)   - Hybrid search
├─ Rerank:           0.045s  (1.3%)   - Reranking
├─ LLM generation:   3.120s  (90.3%)  - Генерация ответа
└─ Post-processing:  0.057s  (1.6%)   - Формирование response
```

---

## 🎯 Применение

### 1. Диагностика узких мест

```
LLM generation: 45.6s  ⚠️ Слишком долго!
→ Решение: Уменьшить контекст, использовать суммаризацию, переключиться на vLLM
```

```
Search: 2.3s  ⚠️ Поиск медленный!
→ Решение: Проверить индексы Qdrant, оптимизировать reranking
```

### 2. Сравнение Ollama vs vLLM

```
Ollama (CPU):
  LLM generation: 26.08s (~6 tokens/sec)

vLLM (GPU):
  LLM generation: 0.78s (~150 tokens/sec)

Speedup: 33x! 🚀
```

### 3. Отладка timeout

```
LLM generation: 301.2s
LLM_TIMEOUT: 300s

→ Проблема: Превысили timeout на 1.2s
→ Решение: Увеличить LLM_TIMEOUT до 360s
```

---

## 📈 Метрики в заголовках HTTP

Каждый response содержит:

```http
HTTP/1.1 200 OK
X-Process-Time: 26.234
...
```

Можно использовать в клиенте:

```typescript
const response = await fetch('/summarize', {...});
const processTime = response.headers.get('X-Process-Time');
console.log(`Request took ${processTime}s`);
```

---

## 🔍 Пример полного лога

### `/ask` с суммаризацией:

```
🌐 🌐 🌐 [40 звездочек]
[HTTP REQUEST ⬇️ ] POST /ask
  ⏰ Request time: 20:30:15.456
  📍 Client: 192.168.65.1
────────────────────────────────────────────────────────────────────────────────

================================================================================
[RAG CONTEXT] Query: 'Расскажи про все проекты'
================================================================================
📚 RETRIEVED DOCUMENTS:
  - Chunks found: 20
  - Context size: ~5200 tokens
  - Model: llama3.1:8b
  - Context window: 8192
  - Summarization threshold: 3000
  - Mode: auto
  [1] project_1 chunk_0: Проект началс я...
  [2] project_2 chunk_5: Бюджет составляет...
  ... и еще 15 чанков
================================================================================

[RAG] Mode: auto. Context 5200 tokens > threshold 3000. Using summarization.

[summarize_chunks] Context: ~5200 tokens, dynamic max_tokens: 1500

[Summarization] Document is large (5200 tokens). Starting Map-Reduce...

... [MAP фаза - 2 чанка] ...

================================================================================
[LLM REQUEST → Ollama] Model: llama3.1:8b
================================================================================
📝 INPUT:
  - Prompt length: 2890 chars, ~580 tokens
  - Max output tokens: 300
  ⏰ Request time: 20:30:15.567
────────────────────────────────────────────────────────────────────────────────
🚀 Sending request to Ollama...
  ⏰ LLM send time: 20:30:15.578

✅ Response received from Ollama!
  ⏰ LLM receive time: 20:30:28.901

⏱️  TIMING BREAKDOWN:
  - Request start:  20:30:15.567
  - LLM send:       20:30:15.578
  - LLM receive:    20:30:28.901
  - Total:          13.323s
================================================================================

... [REDUCE фаза] ...

... [Финальный LLM запрос для ответа пользователю] ...

────────────────────────────────────────────────────────────────────────────────
[HTTP RESPONSE ⬆️ ] POST /ask
  ✅ Status: 200
  ⏱️  Total HTTP time: 32.456s
  ⏰ Response time: 20:30:47.912
🌐 🌐 🌐 [40 звездочек]
```

---

## 🎯 Итого

**Теперь логируется:**

✅ **HTTP уровень** (все endpoints):
- Время поступления запроса
- Время отправки ответа
- Общее время обработки

✅ **LLM уровень** (детально):
- Время начала вызова call_llm()
- Время отправки в Ollama/vLLM
- Время получения ответа
- Breakdown всех этапов

✅ **Метрики**:
- Размеры (chars, tokens)
- Скорость (tokens/sec)
- Временные штампы с миллисекундами

**Работает для Ollama и vLLM одинаково!** ✅

