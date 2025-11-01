# Настройка Ollama с Qwen3:14b для отладки суммаризации

## ✅ Что настроено

### 1. Конфигурация модели в `config/llm_models.json`

Добавлена конфигурация для `qwen3:14b`:

```json
{
  "model_name": "qwen3:14b",
  "provider": "ollama",
  "context_window": 40960,
  "max_output_tokens": 2048,
  "summarization_threshold": 15000,
  "summarization_max_output": 5000,
  "tokens_per_second": 45,
  "supports_streaming": true,
  "supports_function_calling": true
}
```

**Параметры суммаризации:**
- ✅ **context_window**: 40960 токенов (очень большое окно!)
- ✅ **summarization_threshold**: 15000 токенов
  - При превышении 15K токенов в контексте автоматически включается суммаризация
- ✅ **summarization_max_output**: 5000 токенов максимум в summary

### 2. Обновлен `docker-compose.yml`

Модель по умолчанию изменена на `qwen3:14b`:

```yaml
- LLM_MODEL=${LLM_MODEL:-qwen3:14b}
```

### 3. Создан `.env` файл для запуска

Скопировать конфигурацию:

```bash
cp .env.ollama.new .env
```

Или создать вручную `.env`:

```bash
# Configuration for Ollama with Qwen3:14b
LLM_MODE=ollama
LLM_MODEL=qwen3:14b
LLM_TIMEOUT=240
LLM_MAX_TOKENS=2048
LLM_TEMPERATURE=0.7

# IMPORTANT: Context window size (аналог VLLM_MAX_MODEL_LEN для vLLM)
OLLAMA_NUM_CTX=40960

QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=docs
EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
KEYWORD_INDEX_DIR=/data/whoosh_index

CHUNK_TOKENS=500
CHUNK_OVERLAP=50
CONTEXT_MAX_CHUNKS=6
TOP_K_DEFAULT=6

CACHE_ENABLED=true
CACHE_TTL_SECONDS=300
```

## 🚀 Запуск

```bash
# 1. Копировать конфигурацию
cp .env.ollama.new .env

# 2. Запустить контейнеры
make up

# 3. Дождаться готовности
make wait

# 4. Проверить здоровье
make health
```

## 🧪 Проверка конфигурации суммаризации

### Проверить что модель загружена

```bash
curl http://localhost:11434/api/tags | jq '.models[] | .name'
# Должно показать: qwen3:14b
```

### Проверить конфигурацию через API

```bash
curl http://localhost:8000/model-config | jq
```

**Ожидаемый ответ:**

```json
{
  "model_name": "qwen3:14b",
  "provider": "ollama",
  "context_window": 40960,
  "max_output_tokens": 2048,
  "summarization_threshold": 15000,
  "summarization_max_output": 5000,
  "effective_context_for_rag": 38912,
  "recommended_chunk_limit": 129,
  "tokens_per_second": 45
}
```

## 📊 Важные параметры контекстного окна

### OLLAMA_NUM_CTX vs summarization_threshold

**Два разных параметра:**

1. **OLLAMA_NUM_CTX** = 40960 (в .env и docker-compose.yml)
   - Максимальный размер контекстного окна модели Ollama
   - Аналог `VLLM_MAX_MODEL_LEN` для vLLM
   - Определяет сколько токенов может обработать модель за один вызов
   - Для qwen3:14b = 40960 токенов

2. **summarization_threshold** = 15000 (в config/llm_models.json)
   - Порог для автоматической суммаризации в RAG
   - При превышении этого значения включается суммаризация контекста
   - Для qwen3:14b = 15000 токенов (~37% от context_window)

**Почему threshold меньше чем num_ctx?**

```
context_window (40960) = num_ctx
├─ system_prompt (~500 tokens)
├─ max_output_tokens (2048)
├─ RAG context (до ~38000 токенов)
└─ safety margin

summarization_threshold (15000) = ~37% от effective context
```

### Когда срабатывает суммаризация?

**В endpoint `/ask`:**

1. Поиск находит N документов (chunks)
2. Подсчитываются токены в найденных чанках
3. **ЕСЛИ** `context_tokens > 15000`:
   - ✅ Автоматически включается суммаризация
   - Чанки суммаризируются до ~5000 токенов
   - Summary передается в LLM вместо всех чанков
4. **ИНАЧЕ** (< 15000 токенов):
   - Обычный RAG (чанки передаются как есть)

### Пример

```bash
# Запрос с большим top_k (много контекста)
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "q": "Расскажи про все проекты",
    "space_id": "space_demo",
    "top_k": 50
  }' | jq

# Response будет содержать:
{
  "answer": "...",
  "summarized": true,        # Была ли суммаризация
  "context_tokens": 18500,   # Исходный размер контекста
  "model": "qwen3:14b"
}
```

## 🎯 Готовность к отладке 6 паттернов

С этой конфигурацией можно тестировать все 6 паттернов суммаризации:

1. ✅ **Паттерн 1**: Прямая суммаризация (`/summarize`)
2. ✅ **Паттерн 2**: Smart Context Compression (автоматически в `/ask` при > 15K токенов)
3. ✅ **Паттерн 3**: Режимы работы (`/ask?mode=auto|normal|summarize|detailed`)
4. ✅ **Паттерн 4**: Pre-computed summaries (кэширование в Qdrant)
5. ✅ **Паттерн 5**: Потоковая суммаризация (`/summarize-stream`)
6. ✅ **Паттерн 6**: Суммаризация тредов (`/thread/summarize`)

---

**Следующий шаг:** Запустить контейнеры и протестировать каждый паттерн! 🚀

