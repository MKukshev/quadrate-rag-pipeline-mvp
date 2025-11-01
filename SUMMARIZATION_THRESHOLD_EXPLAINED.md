# Как работает порог суммаризации (summarization_threshold)

## 📋 TL;DR

**Порог суммаризации для ВСЕХ конфигураций (Ollama и vLLM) берётся из `config/llm_models.json`**

---

## 🔍 Детальное объяснение

### 1. Где хранится конфигурация?

**Файл:** `config/llm_models.json`

Содержит конфигурации для всех поддерживаемых моделей:
- Ollama модели (qwen3:14b, llama3.1:8b, mistral:7b)
- vLLM модели (openai/gpt-oss-20b, Meta-Llama-3.1-8B, Mixtral-8x7B)
- Cloud модели (gpt-4, claude-3)

### 2. Как определяется текущая модель?

**Переменные окружения (.env или docker-compose.yml):**

```bash
# Для Ollama
LLM_MODE=ollama
LLM_MODEL=qwen3:14b

# Для vLLM
LLM_MODE=vllm
LLM_MODEL=openai/gpt-oss-20b
```

### 3. Как загружается конфигурация?

**Код в `backend/services/llm_config.py`:**

```python
def get_current_model_config() -> LLMModelConfig:
    """
    Get configuration for currently active LLM model
    Reads from environment variables LLM_MODE and LLM_MODEL
    """
    from . import config
    
    registry = get_llm_registry()  # Загружает llm_models.json
    return registry.get_or_default(config.LLM_MODE, config.LLM_MODEL)
```

**Процесс:**
1. Читает `LLM_MODE` и `LLM_MODEL` из переменных окружения
2. Ищет `{provider}::{model_name}` в registry
3. Возвращает конфигурацию (или defaults если не найдено)

### 4. Где используется порог?

**Код в `backend/app.py` (endpoint `/ask`):**

```python
# Строка 256: Получить конфигурацию модели
model_config = get_current_model_config()

# Строка 276: Проверка порога (режим "auto")
should_summarize = context_tokens > model_config.summarization_threshold

if should_summarize:
    # Суммаризировать контекст
    summary = summarize_chunks(fused, query=req.q)
    prompt = build_prompt_with_summary(summary, req.q)
else:
    # Обычный RAG
    prompt = build_prompt(fused, req.q)
```

---

## 📊 Примеры конфигураций

### Ollama: qwen3:14b

```json
{
  "model_name": "qwen3:14b",
  "provider": "ollama",
  "context_window": 40960,
  "max_output_tokens": 2048,
  "summarization_threshold": 15000,
  "summarization_max_output": 5000
}
```

**Поведение:**
- Если контекст ≤ 15000 токенов → обычный RAG
- Если контекст > 15000 токенов → суммаризация

### vLLM: openai/gpt-oss-20b

```json
{
  "model_name": "openai/gpt-oss-20b",
  "provider": "vllm",
  "context_window": 8192,
  "max_output_tokens": 512,
  "summarization_threshold": 3000,
  "summarization_max_output": 1500
}
```

**Поведение:**
- Если контекст ≤ 3000 токенов → обычный RAG
- Если контекст > 3000 токенов → суммаризация

### vLLM: mistralai/Mistral-7B-Instruct-v0.3

```json
{
  "model_name": "mistralai/Mistral-7B-Instruct-v0.3",
  "provider": "vllm",
  "context_window": 32768,
  "max_output_tokens": 1024,
  "summarization_threshold": 12000,
  "summarization_max_output": 4000
}
```

**Поведение:**
- Если контекст ≤ 12000 токенов → обычный RAG
- Если контекст > 12000 токенов → суммаризация

---

## 🔧 Два разных параметра

### Не путать!

| Что | Где настраивается | Для чего |
|-----|-------------------|----------|
| **Context Window** | `.env` → `VLLM_MAX_MODEL_LEN` или `OLLAMA_NUM_CTX` | Размер контекстного окна LLM сервера |
| **Summarization Threshold** | `llm_models.json` → `summarization_threshold` | Порог для включения суммаризации в RAG |

### Для vLLM

```yaml
# docker-compose.vllm-mig.yml
vllm-medium:
  environment:
    - VLLM_MODEL=openai/gpt-oss-20b
    - VLLM_MAX_MODEL_LEN=8192  # ← Context window сервера
```

```json
// config/llm_models.json
{
  "model_name": "openai/gpt-oss-20b",
  "context_window": 8192,           // ← Должно совпадать
  "summarization_threshold": 3000   // ← Порог суммаризации (~37%)
}
```

### Для Ollama

```yaml
# docker-compose.yml
backend:
  environment:
    - LLM_MODEL=qwen3:14b
    - OLLAMA_NUM_CTX=40960  # ← Context window при вызовах
```

```json
// config/llm_models.json
{
  "model_name": "qwen3:14b",
  "context_window": 40960,          // ← Должно совпадать
  "summarization_threshold": 15000  // ← Порог суммаризации (~37%)
}
```

---

## ✅ Проверка конфигурации

### API endpoint для проверки

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
  "effective_context_for_rag": 38912,
  "summarization_threshold": 15000,
  "summarization_max_output": 5000,
  "recommended_chunk_limit": 129,
  "tokens_per_second": 45
}
```

### Проверка в логах

При вызове `/ask` с режимом `auto`:

```bash
curl -X POST http://localhost:8000/ask \
  -d '{"q":"test","space_id":"demo","mode":"auto","top_k":20}'
```

**В логах backend будет:**

```
[RAG] Mode: auto. Context 5000 tokens ≤ threshold 15000. Using normal RAG.
# или
[RAG] Mode: auto. Context 18000 tokens > threshold 15000. Using summarization.
```

---

## 🎯 Как добавить новую модель?

### 1. Добавить в llm_models.json

```json
{
  "model_name": "your-model-name",
  "provider": "vllm",  // или "ollama"
  "context_window": 16384,
  "max_output_tokens": 1024,
  "summarization_threshold": 6000,  // ~37-40% от effective context
  "summarization_max_output": 3000,
  "tokens_per_second": 200,
  "supports_streaming": true,
  "supports_function_calling": true,
  "description": "Your model description"
}
```

### 2. Обновить .env

```bash
LLM_MODE=vllm
LLM_MODEL=your-model-name
VLLM_MAX_MODEL_LEN=16384  # Должно совпадать с context_window
```

### 3. Проверить

```bash
make up
make wait
curl http://localhost:8000/model-config | jq
```

---

## 📚 Связанные документы

- `config/llm_models.json` - конфигурации моделей
- `backend/services/llm_config.py` - загрузка конфигураций
- `backend/app.py` - использование порога в `/ask`
- `CONTEXT_WINDOW_CONFIGURATION.md` - настройка контекстных окон
- `OLLAMA_QWEN3_SETUP.md` - настройка Ollama

---

**Вывод:** Порог суммаризации ВСЕГДА в `llm_models.json`, независимо от Ollama или vLLM! 🎯

