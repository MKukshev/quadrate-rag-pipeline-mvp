# Конфигурация контекстного окна: Ollama vs vLLM

## 📋 Что было сделано

### Проблема
Для vLLM был параметр `VLLM_MAX_MODEL_LEN`, определяющий размер контекстного окна, но для Ollama аналогичного параметра не было настроено.

### Решение
Добавлен параметр **`OLLAMA_NUM_CTX`** - аналог `VLLM_MAX_MODEL_LEN` для Ollama.

---

## 🔧 Изменения в коде

### 1. `backend/services/config.py`

Добавлена новая переменная окружения:

```python
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "40960"))  # Context window for Ollama
```

### 2. `backend/services/rag.py`

Добавлено использование `OLLAMA_NUM_CTX` в API запросах к Ollama:

```python
# Импорт
from .config import (
    ...
    OLLAMA_NUM_CTX,
)

# Использование в call_llm()
r = requests.post(
    "http://ollama:11434/api/generate",
    json={
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": LLM_STREAM_ENABLED,
        "options": {
            "num_predict": LLM_MAX_TOKENS,
            "num_ctx": OLLAMA_NUM_CTX,  # ← NEW
        },
    },
    ...
)
```

### 3. `docker-compose.yml`

Добавлена переменная окружения для backend контейнера:

```yaml
environment:
  - LLM_MODE=ollama
  - LLM_MODEL=${LLM_MODEL:-qwen3:14b}
  - OLLAMA_NUM_CTX=${OLLAMA_NUM_CTX:-40960}  # ← NEW
  ...
```

### 4. `.env.ollama.new`

Добавлен параметр в конфигурационный файл:

```bash
OLLAMA_NUM_CTX=40960
```

---

## 📊 Сравнение параметров

### vLLM (docker-compose.vllm-mig.yml)

```yaml
vllm-medium:
  environment:
    - VLLM_MODEL=${VLLM_MODEL_MEDIUM:-OpenGPT/gpt-oss-20b}
    - VLLM_MAX_MODEL_LEN=${VLLM_MAX_MODEL_LEN_MEDIUM:-8192}  # ← Context window
```

**Где используется:**
- Передается в vLLM сервер при запуске
- `--max-model-len ${VLLM_MAX_MODEL_LEN}`

### Ollama (docker-compose.yml)

```yaml
backend:
  environment:
    - LLM_MODE=ollama
    - LLM_MODEL=${LLM_MODEL:-qwen3:14b}
    - OLLAMA_NUM_CTX=${OLLAMA_NUM_CTX:-40960}  # ← Context window
```

**Где используется:**
- Передается в Ollama API при каждом вызове
- `options: { "num_ctx": OLLAMA_NUM_CTX }`

---

## 🎯 Два разных параметра!

### ВАЖНО: Context Window ≠ Summarization Threshold

| Параметр | Где | Значение | Назначение |
|----------|-----|----------|------------|
| **OLLAMA_NUM_CTX** | `.env` + `docker-compose.yml` | 40960 | Максимальный размер контекстного окна модели |
| **summarization_threshold** | `config/llm_models.json` | 15000 | Порог для включения авто-суммаризации |

### Почему threshold меньше?

```
OLLAMA_NUM_CTX = 40960 токенов (100%)
├─ system_prompt: ~500 токенов
├─ max_output_tokens: 2048 токенов  
├─ safety margin: ~500 токенов
└─ effective_context: ~38000 токенов (93%)

summarization_threshold = 15000 токенов (~37% от context_window)
```

**Причина:**
- Суммаризация включается раньше, чем заполняется весь контекст
- Оставляет запас для промпта, вывода и безопасности
- Оптимизирует скорость и качество ответов

---

## 🔍 Для qwen3:14b

### Параметры модели (из Ollama API)

```json
{
  "qwen3.context_length": 40960,
  "parameter_size": "14.8B",
  "quantization": "Q4_K_M"
}
```

### Конфигурация в llm_models.json

```json
{
  "model_name": "qwen3:14b",
  "provider": "ollama",
  "context_window": 40960,          // ← Соответствует OLLAMA_NUM_CTX
  "max_output_tokens": 2048,
  "summarization_threshold": 15000,  // ← 37% от context_window
  "summarization_max_output": 5000
}
```

### В .env файле

```bash
# Context window для модели
OLLAMA_NUM_CTX=40960

# Выход модели за один запрос
LLM_MAX_TOKENS=2048
```

---

## 🎯 Важно: Единый источник конфигурации!

### Для ОБЕИХ конфигураций (Ollama и vLLM)

Порог суммаризации (`summarization_threshold`) **ВСЕГДА** берётся из `config/llm_models.json`.

**Как это работает:**

1. Backend читает переменные окружения:
   - `LLM_MODE` (ollama/vllm)
   - `LLM_MODEL` (qwen3:14b / openai/gpt-oss-20b)

2. Функция `get_current_model_config()` ищет соответствующую конфигурацию в `llm_models.json`

3. Использует `summarization_threshold` из найденной конфигурации

**Пример для Ollama:**
```bash
# .env
LLM_MODE=ollama
LLM_MODEL=qwen3:14b

# → Ищет в llm_models.json:
{
  "model_name": "qwen3:14b",
  "provider": "ollama",
  "summarization_threshold": 15000  # ← Используется это значение
}
```

**Пример для vLLM:**
```bash
# .env
LLM_MODE=vllm
LLM_MODEL=openai/gpt-oss-20b

# → Ищет в llm_models.json:
{
  "model_name": "openai/gpt-oss-20b",
  "provider": "vllm",
  "summarization_threshold": 3000  # ← Используется это значение
}
```

### Где используется порог суммаризации?

**В коде backend/app.py:**

```python
# Строка 256
model_config = get_current_model_config()  # Читает из llm_models.json

# Строка 276 (режим "auto")
should_summarize = context_tokens > model_config.summarization_threshold

# Если context_tokens > threshold → включается суммаризация
```

### VLLM_MAX_MODEL_LEN vs summarization_threshold

**Два разных параметра!**

| Параметр | Где | Для чего |
|----------|-----|----------|
| `VLLM_MAX_MODEL_LEN` | .env → vLLM server | Размер контекстного окна сервера vLLM |
| `summarization_threshold` | llm_models.json | Порог для автоматической суммаризации в RAG |

**Аналогия для Ollama:**

| Параметр | Где | Для чего |
|----------|-----|----------|
| `OLLAMA_NUM_CTX` | .env → Ollama API | Размер контекстного окна при вызове Ollama |
| `summarization_threshold` | llm_models.json | Порог для автоматической суммаризации в RAG |

---

## ✅ Проверка конфигурации

### 1. Проверить что параметр установлен

```bash
# В контейнере backend
docker compose exec backend env | grep OLLAMA_NUM_CTX
# Должно показать: OLLAMA_NUM_CTX=40960
```

### 2. Проверить в логах Ollama

```bash
# После вызова LLM увидите в логах
curl -X POST http://localhost:8000/ask -d '{"q":"test","space_id":"demo"}'

# В логах Ollama будет видно:
# "num_ctx": 40960
```

### 3. Проверить конфигурацию модели

```bash
curl http://localhost:8000/model-config | jq
```

**Ожидаемый ответ:**

```json
{
  "model_name": "qwen3:14b",
  "context_window": 40960,
  "summarization_threshold": 15000,
  "effective_context_for_rag": 38912
}
```

---

## 🚀 Готово к использованию!

Теперь:
- ✅ Ollama имеет явно настроенное контекстное окно (40960)
- ✅ Аналогично vLLM (VLLM_MAX_MODEL_LEN)
- ✅ Порог суммаризации настроен корректно (15000)
- ✅ Конфигурация совместима с vLLM MIG setup
- ✅ Готово к отладке 6 паттернов суммаризации!

**Следующий шаг:** Запустить и протестировать! 🎯

