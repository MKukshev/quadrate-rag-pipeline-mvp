# Чеклист совместимости с vLLM MIG

**Статус:** ✅ Локальная проверка пройдена  
**Требуется:** Проверка на GPU сервере с NVIDIA MIG

---

## ✅ Что проверено локально (без GPU)

### 1. Синтаксис docker-compose.vllm-mig.yml
```bash
docker compose -f docker-compose.vllm-mig.yml config
```
**Результат:** ✅ Валиден, ошибок нет

### 2. Код совместим с vLLM и Ollama
**Проверено:**
- ✅ `call_llm()` поддерживает оба режима (LLM_MODE=ollama/vllm)
- ✅ Динамический max_tokens работает для обоих
- ✅ Language detection универсален
- ✅ Логирование одинаковое

### 3. Параметры синхронизированы

**Добавлено в vLLM MIG:**
- ✅ `PYTHONUNBUFFERED=1` - для real-time логов
- ✅ `LLM_MAX_TOKENS=${LLM_MAX_TOKENS:-2048}` - увеличено с 512

### 4. Конфигурация моделей

**В `config/llm_models.json` добавлены:**
- ✅ `openai/gpt-oss-20b` (MEDIUM model)
- ✅ `OpenGPT/gpt-oss-20b` (альтернативное имя)
- ✅ `mistralai/Mistral-7B-Instruct-v0.3` (SMALL model)

---

## 🔍 Что нужно проверить на GPU сервере

### Шаг 1: Запуск vLLM MIG

```bash
# На GPU сервере с NVIDIA MIG
cd /path/to/project

# Скопировать .env для vLLM MIG
cp .env.vllm-mig .env

# Запустить
docker compose -f docker-compose.vllm-mig.yml up -d

# Проверить логи
docker compose -f docker-compose.vllm-mig.yml logs -f vllm-medium
docker compose -f docker-compose.vllm-mig.yml logs -f vllm-small
docker compose -f docker-compose.vllm-mig.yml logs -f backend
```

**Ожидаемо:** Контейнеры запускаются без ошибок

---

### Шаг 2: Проверить health

```bash
# vLLM MEDIUM (port 8001)
curl http://localhost:8001/health

# vLLM SMALL (port 8002)
curl http://localhost:8002/health

# Backend
curl http://localhost:8000/health
```

**Ожидаемо:** Все возвращают 200 OK

---

### Шаг 3: Проверить model config

```bash
curl http://localhost:8000/model-config | jq
```

**Ожидаемо:**
```json
{
  "model_name": "openai/gpt-oss-20b",
  "provider": "vllm",
  "context_window": 8192,
  "summarization_threshold": 3000,
  "summarization_max_output": 1500
}
```

---

### Шаг 4: Тест Паттерна 1 (прямая суммаризация)

```bash
# Загрузить документ
curl -X POST http://localhost:8000/ingest \
  -F "file=@test_doc.md" \
  -F "space_id=gpu_test"

# Получить doc_id из ответа, затем:
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "...",
    "space_id": "gpu_test"
  }' | jq
```

**Ожидаемо:**
- ✅ Summary генерируется
- ✅ На том же языке что и документ
- ✅ Скорость: 150-250 tok/s (vs 0.8-4.8 на Ollama)
- ✅ Логи показывают: `[LLM REQUEST → vLLM]`
- ✅ Timing breakdown работает

---

### Шаг 5: Тест Паттерна 2-3 (/ask с режимами)

```bash
# Mode: auto (с автоматической суммаризацией)
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "q": "Расскажи подробно обо всем",
    "space_id": "gpu_test",
    "mode": "auto",
    "top_k": 30
  }' | jq '{summarized, context_tokens, mode}'

# Mode: summarize (принудительная)
curl -X POST http://localhost:8000/ask \
  -d '{"q":"Дай краткий обзор","mode":"summarize"}' | jq '{summarized, mode}'
```

**Ожидаемо:**
- ✅ `summarized: true/false` в зависимости от режима
- ✅ Логи: `[RAG CONTEXT]` → `[RAG] Mode: ...` → `[LLM REQUEST → vLLM]`

---

### Шаг 6: Тест Паттерна 4 (Pre-computed)

```bash
# С генерацией summary
curl -X POST http://localhost:8000/ingest \
  -F "file=@large_doc.pdf" \
  -F "space_id=gpu_test" \
  -F "generate_summary=true"

# Подождать background task (проверить логи)
docker compose -f docker-compose.vllm-mig.yml logs backend | grep Background

# Проверить кэш
curl -X POST http://localhost:8000/summarize \
  -d '{"doc_id":"...","space_id":"gpu_test"}' | jq '{cached}'
```

**Ожидаемо:**
- ✅ `summary_pending: true` при индексации
- ✅ Background task запускается
- ✅ `cached: true` при повторном запросе
- ✅ Скорость с кэшем: < 0.1s

---

### Шаг 7: Тест Паттерна 5 (Streaming)

```bash
curl -N -X POST http://localhost:8000/summarize-stream \
  -d '{"doc_id":"...","space_id":"gpu_test"}'
```

**Ожидаемо:**
- ✅ События: start → processing → summary → complete
- ✅ Русский текст читаемый (не \uXXXX)
- ✅ ETA показывается
- ✅ Скорость генерации намного выше

---

### Шаг 8: Проверить логирование

**Смотреть логи backend:**
```bash
docker compose -f docker-compose.vllm-mig.yml logs -f backend
```

**Ожидаемо в логах:**
```
🌐 [40 звездочек]
[HTTP REQUEST ⬇️ ] POST /summarize
  ⏰ Request time: HH:MM:SS.mmm  ← СРАЗУ появляется!

[Language Detection] Input text language: ru (Русский)

[DYNAMIC MAX_TOKENS CALCULATION]
📐 Formula: available = context_window - prompt_tokens - safety_margin
  context_window  = 8,192
  prompt_tokens   =   X
  ...

[LLM REQUEST → vLLM] Model: openai/gpt-oss-20b
📝 INPUT:
  - Prompt: X chars, ~Y tokens
  - Max output tokens: Z
🚀 Sending request to vLLM...
  ⏰ LLM send time: HH:MM:SS.mmm

✅ Response received from vLLM!
  ⏰ LLM receive time: HH:MM:SS.mmm

[LLM RESPONSE ← vLLM]
📤 OUTPUT:
  - Response: A chars, ~B tokens
  - Generation time: C.Cs  ← Должно быть < 1s!
  - Speed: ~150-250 tokens/sec  ← Намного быстрее!

[HTTP RESPONSE ⬆️ ]
  ⏱️  Total HTTP time: X.Xs
```

---

## ⚠️ Что добавить в vLLM MIG конфигурацию

### Обновления нужные:

<function_calls>
<invoke name="search_replace">
<parameter name="file_path">/Users/maksimkuksev/cursor/ai-assistant-mvp/docker-compose.vllm-mig.yml
