# Детальное логирование LLM запросов

## ✅ Что добавлено

Детальное логирование **всего** что происходит при вызове LLM:
- 📝 INPUT: что отправляется в LLM
- 📤 OUTPUT: что получаем в ответе
- ⏱️ Метрики: время, скорость, размеры

---

## 📋 Формат логов

### 1. RAG Context (в /ask endpoint)

```
================================================================================
[RAG CONTEXT] Query: 'Какой бюджет проекта?'
================================================================================
📚 RETRIEVED DOCUMENTS:
  - Chunks found: 3
  - Context size: ~450 tokens
  - Model: llama3.1:8b
  - Context window: 8192
  - Summarization threshold: 3000
  - Mode: auto
  [1] test_doc_564945be chunk_0: # Тестовый документ для суммаризации

## Проект Alpha

Проект Alpha начался 1 ...
  [2] test_doc_564945be chunk_1: ...
  [3] SUMMARIZATION_COMPLETE_GUIDE_eda9ebe5 chunk_0: ...
================================================================================
```

### 2. LLM Request (что отправляем)

```
================================================================================
[LLM REQUEST → Ollama] Model: llama3.1:8b
================================================================================
📝 INPUT:
  - Prompt length: 1234 chars, ~456 tokens
  - Max output tokens: 2048
  - Context window: 8192
  - Timeout: 300s
────────────────────────────────────────────────────────────────────────────────
PROMPT PREVIEW (first 500 chars):
Ты — ассистент, отвечай строго по предоставленному КОНТЕКСТУ. 
Если данных недостаточно — так и скажи.

КОНТЕКСТ:
[1] doc_id=test_doc_564945be chunk=0 type=technical_docs
"# Тестовый документ для суммаризации..."

ВОПРОС:
Какой бюджет проекта?

Ответь кратко и по делу...
================================================================================
```

### 3. LLM Response (что получаем)

```
================================================================================
[LLM RESPONSE ← Ollama]
================================================================================
📤 OUTPUT:
  - Response length: 123 chars, ~25 tokens
  - Generation time: 3.45s
  - Speed: ~7.2 tokens/sec
────────────────────────────────────────────────────────────────────────────────
RESPONSE PREVIEW (first 500 chars):
Based on the context, Project Alpha has a budget of $200,000.
This budget was established at the start of the project on March 1, 2025.
================================================================================
```

---

## 🎯 Что логируется

### INPUT (запрос в LLM):

| Метрика | Описание |
|---------|----------|
| **Prompt length** | Размер промпта в символах и токенах |
| **Max output tokens** | Лимит на ответ (динамический или фиксированный) |
| **Context window** | Размер контекстного окна модели |
| **Timeout** | Максимальное время ожидания |
| **Prompt preview** | Первые 500 символов промпта |

### OUTPUT (ответ от LLM):

| Метрика | Описание |
|---------|----------|
| **Response length** | Размер ответа в символах и токенах |
| **Generation time** | Время генерации в секундах |
| **Speed** | Скорость генерации (токенов/сек) |
| **Response preview** | Первые 500 символов ответа |

### RAG Context (для /ask):

| Метрика | Описание |
|---------|----------|
| **Query** | Запрос пользователя |
| **Chunks found** | Количество найденных чанков |
| **Context size** | Размер контекста в токенах |
| **Model info** | Модель, context window, threshold |
| **Mode** | Режим работы (auto/normal/summarize) |
| **Chunks preview** | Предпросмотр первых 5 чанков |

---

## 🔍 Примеры логов

### Пример 1: Обычный RAG (без суммаризации)

```bash
curl -X POST /ask -d '{"q":"Какой бюджет?","space_id":"demo","mode":"auto"}'
```

**Логи:**

```
================================================================================
[RAG CONTEXT] Query: 'Какой бюджет?'
================================================================================
📚 RETRIEVED DOCUMENTS:
  - Chunks found: 3
  - Context size: ~450 tokens
  - Model: llama3.1:8b
  - Context window: 8192
  - Summarization threshold: 3000
  - Mode: auto
  [1] test_doc_564945be chunk_0: # Тестовый документ...
  [2] test_doc_564945be chunk_1: ...
  [3] test_doc_564945be chunk_2: ...
================================================================================

[RAG] Mode: auto. Context 450 tokens ≤ threshold 3000. Using normal RAG.

================================================================================
[LLM REQUEST → Ollama] Model: llama3.1:8b
================================================================================
📝 INPUT:
  - Prompt length: 678 chars, ~156 tokens
  - Max output tokens: 2048
  - Context window: 8192
  - Timeout: 300s
────────────────────────────────────────────────────────────────────────────────
PROMPT PREVIEW (first 500 chars):
Ты — ассистент, отвечай строго по предоставленному КОНТЕКСТУ...
================================================================================

================================================================================
[LLM RESPONSE ← Ollama]
================================================================================
📤 OUTPUT:
  - Response length: 89 chars, ~18 tokens
  - Generation time: 2.34s
  - Speed: ~7.7 tokens/sec
────────────────────────────────────────────────────────────────────────────────
RESPONSE PREVIEW (first 500 chars):
Based on the context, Project Alpha has a budget of $200,000.
================================================================================
```

### Пример 2: С автоматической суммаризацией

```bash
curl -X POST /ask -d '{"q":"Расскажи все про проект","mode":"auto","top_k":20}'
```

**Логи:**

```
================================================================================
[RAG CONTEXT] Query: 'Расскажи все про проект'
================================================================================
📚 RETRIEVED DOCUMENTS:
  - Chunks found: 20
  - Context size: ~5500 tokens
  - Model: llama3.1:8b
  - Context window: 8192
  - Summarization threshold: 3000
  - Mode: auto
  [1] doc_1 chunk_0: ...
  [2] doc_2 chunk_3: ...
  ... и еще 15 чанков
================================================================================

[RAG] Mode: auto. Context 5500 tokens > threshold 3000. Using summarization.

[summarize_chunks] Context: ~5500 tokens, dynamic max_tokens: 1500

[Summarization] Document is large (5500 tokens). Starting Map-Reduce...
[Summarization] Split into 2 chunks
[Summarization] Processing chunk 1/2...

[Summarization] Dynamic max_tokens: 300 (requested: 300, available: 3500)

================================================================================
[LLM REQUEST → Ollama] Model: llama3.1:8b
================================================================================
📝 INPUT:
  - Prompt length: 2890 chars, ~650 tokens
  - Max output tokens: 300
  - Context window: 8192
  - Timeout: 300s
────────────────────────────────────────────────────────────────────────────────
PROMPT PREVIEW (first 500 chars):
Summarize the following text concisely in approximately 300 words or less...
================================================================================

================================================================================
[LLM RESPONSE ← Ollama]
================================================================================
📤 OUTPUT:
  - Response length: 567 chars, ~95 tokens
  - Generation time: 8.23s
  - Speed: ~11.5 tokens/sec
────────────────────────────────────────────────────────────────────────────────
RESPONSE PREVIEW (first 500 chars):
Part 1 summary: Project Alpha is a software development initiative with a $200K budget...
================================================================================

[Summarization] Processing chunk 2/2...
[... повторяется для chunk 2 ...]

[Summarization] REDUCE phase: Combining 2 summaries...
[Summarization] Final summary max_tokens: 800

[... финальная суммаризация ...]

================================================================================
[LLM REQUEST → Ollama] Model: llama3.1:8b
================================================================================
📝 INPUT:
  - Prompt length: 1456 chars, ~312 tokens
  - Max output tokens: 2048
  - Context window: 8192
  - Timeout: 300s
────────────────────────────────────────────────────────────────────────────────
PROMPT PREVIEW (first 500 chars):
Ты — ассистент, отвечай строго по предоставленному КОНТЕКСТУ...
КОНТЕКСТ (суммаризировано из 20 найденных фрагментов):
[Final summary here...]
================================================================================

================================================================================
[LLM RESPONSE ← Ollama]
================================================================================
📤 OUTPUT:
  - Response length: 345 chars, ~67 tokens
  - Generation time: 5.67s
  - Speed: ~11.8 tokens/sec
────────────────────────────────────────────────────────────────────────────────
RESPONSE PREVIEW (first 500 chars):
Project Alpha is a $200,000 software development project that started March 1, 2025...
================================================================================
```

---

## 🎯 Польза для отладки

### 1. Видно точный размер контекста

Можем проверить:
- Действительно ли контекст превышает threshold?
- Сколько токенов уходит на промпт vs ответ?
- Влезает ли всё в context_window?

### 2. Диагностика проблем

```
# Если ответ обрезан:
Response length: 2048 chars, ~512 tokens  
→ Достиг лимита max_tokens! Нужно увеличить.

# Если timeout:
Generation time: 301.23s
→ Превысил LLM_TIMEOUT! Увеличить или упростить промпт.

# Если контекст не влезает:
Prompt: ~7500 tokens, Max output: 2048
Total: 9548 > Context window: 8192
→ Нужна суммаризация!
```

### 3. Оптимизация производительности

```
Speed: ~7.2 tokens/sec  (llama3.1:8b на CPU)
Speed: ~150 tokens/sec  (vLLM на GPU)

→ Видим разницу и можем принять решение о миграции на GPU
```

---

## 📊 Метрики в логах

### Для каждого LLM вызова:

```
INPUT:
  Prompt: X chars, ~Y tokens
  Max output: Z tokens
  Context window: W tokens
  
  Проверка: Y + Z < W ✅ (должно влезать)

OUTPUT:
  Response: A chars, ~B tokens
  Time: C seconds
  Speed: B/C tokens/sec
  
  Проверка: B ≤ Z ✅ (не превысил лимит)
```

---

## 🔧 Управление логированием

### Отключить детальные логи (production):

Можно добавить переменную окружения:

```python
# В config.py
VERBOSE_LLM_LOGGING = os.getenv("VERBOSE_LLM_LOGGING", "true").lower() == "true"

# В rag.py
if VERBOSE_LLM_LOGGING:
    print(f"[LLM REQUEST] ...")
```

```yaml
# docker-compose.yml
environment:
  - VERBOSE_LLM_LOGGING=false  # Отключить в production
```

---

## 🎉 Готово к использованию!

Теперь при каждом вызове LLM вы будете видеть:

1. **Что отправляется:**
   - Точный размер промпта
   - Лимиты на ответ
   - Предпросмотр промпта

2. **Что получаем:**
   - Размер ответа
   - Время генерации
   - Скорость
   - Предпросмотр ответа

3. **RAG контекст:**
   - Найденные документы
   - Размер контекста
   - Будет ли суммаризация

**Смотрите логи:** `docker compose logs -f backend`

