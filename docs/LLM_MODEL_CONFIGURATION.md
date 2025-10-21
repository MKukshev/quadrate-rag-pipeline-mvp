# Конфигурация LLM моделей

## 🎯 Концепция

Каждая LLM модель имеет свои характеристики:
- **Context window** - размер контекстного окна
- **Max output tokens** - максимум токенов в ответе
- **Throughput** - скорость генерации

Эти параметры влияют на работу RAG пайплайна, особенно на:
- Когда использовать суммаризацию
- Сколько чанков отправлять в LLM
- Оптимизацию производительности

---

## 📊 Конфигурация моделей

### Файл конфигурации
📁 `config/llm_models.json`

### Структура

```json
{
  "models": [
    {
      "model_name": "llama3.1:8b",
      "provider": "ollama",
      "context_window": 8192,
      "max_output_tokens": 512,
      "summarization_threshold": 3000,
      "summarization_max_output": 1500,
      "tokens_per_second": 50,
      "description": "..."
    }
  ]
}
```

---

## 🔧 Параметры модели

| Параметр | Описание | Пример |
|----------|----------|--------|
| `context_window` | Полный размер контекстного окна | 8192 |
| `max_output_tokens` | Максимум токенов в ответе | 512 |
| `summarization_threshold` | Порог токенов для авто-суммаризации | 3000 |
| `summarization_max_output` | Макс токенов в summary | 1500 |
| `tokens_per_second` | Скорость генерации | 50-250 |

### Вычисляемые параметры

```python
effective_context_for_rag = context_window - max_output_tokens - 500 (overhead)

# Пример для llama3.1:8b:
# 8192 - 512 - 500 = 7180 токенов доступно для контекста
```

---

## 📋 Предустановленные модели

### Ollama Models

| Модель | Context | Threshold | Use Case |
|--------|---------|-----------|----------|
| **llama3.1:8b** | 8K | 3K | Общее использование |
| **llama3.1:70b** | 8K | 3K | Высокое качество |
| **mistral:7b** | 8K | 3K | Быстрая генерация |
| **qwen2.5:7b** | 32K | 12K | Длинные документы |

### vLLM Models (GPU)

| Модель | Context | Threshold | Use Case |
|--------|---------|-----------|----------|
| **Llama-3.1-8B** | 8K | 3K | Высокая скорость |
| **Llama-3.1-70B-FP8** | 16K | 6K | Большой контекст |
| **Mixtral-8x7B** | 32K | 12K | Очень большой контекст |

### Cloud Models (для справки)

| Модель | Context | Threshold | Cost |
|--------|---------|-----------|------|
| **GPT-4** | 8K | 3K | $0.03/1K |
| **GPT-4 Turbo** | 128K | 50K | $0.01/1K |
| **Claude 3 Sonnet** | 200K | 80K | $0.003/1K |

---

## 🎯 Как работает автоматическая суммаризация

### Алгоритм

```python
# 1. Получить конфигурацию текущей модели
model_config = get_current_model_config()
# → llama3.1:8b: threshold=3000

# 2. Подсчитать токены в контексте
context_tokens = count_tokens(search_results)
# → 5000 токенов

# 3. Сравнить с порогом
if context_tokens > model_config.summarization_threshold:  # 5000 > 3000
    # Суммаризировать
    summary = summarize(results, max_tokens=model_config.summarization_max_output)
    # → 1500 токенов
else:
    # Обычный RAG
    use_all_chunks()
```

### Пример для разных моделей

#### Llama 3.1 8B (context 8K)
```
Search results: 5000 tokens
Threshold: 3000 tokens
Action: ✅ Суммаризация (5000 > 3000)
Output: 1500 tokens
```

#### Mixtral 8x7B (context 32K)
```
Search results: 5000 tokens
Threshold: 12000 tokens
Action: ❌ Обычный RAG (5000 < 12000)
Output: 5000 tokens as-is
```

#### GPT-4 Turbo (context 128K)
```
Search results: 5000 tokens
Threshold: 50000 tokens
Action: ❌ Обычный RAG (5000 < 50000)
Output: 5000 tokens as-is
```

**Вывод:** Модели с большим context window реже используют суммаризацию!

---

## 🔍 Просмотр конфигурации

### API Endpoint

```bash
curl http://localhost:8000/model-config | jq
```

**Response для llama3.1:8b:**
```json
{
  "model_name": "llama3.1:8b",
  "provider": "ollama",
  "context_window": 8192,
  "max_output_tokens": 512,
  "effective_context_for_rag": 7180,
  "summarization_threshold": 3000,
  "summarization_max_output": 1500,
  "recommended_chunk_limit": 23,
  "tokens_per_second": 50,
  "supports_streaming": true,
  "supports_function_calling": false,
  "description": "Llama 3.1 8B via Ollama - balanced performance for general use"
}
```

---

## ⚙️ Добавление своей модели

### Через JSON файл

Отредактируйте `config/llm_models.json`:

```json
{
  "models": [
    {
      "model_name": "your-custom-model",
      "provider": "ollama",
      "context_window": 16384,
      "max_output_tokens": 1024,
      "summarization_threshold": 6000,
      "summarization_max_output": 3000,
      "tokens_per_second": 100,
      "supports_streaming": true,
      "description": "Your custom model description"
    }
  ]
}
```

### Программно

```python
from backend.services.llm_config import get_llm_registry, LLMModelConfig

registry = get_llm_registry()

registry.register(LLMModelConfig(
    model_name="custom-model:13b",
    provider="ollama",
    context_window=16384,
    max_output_tokens=1024,
    summarization_threshold=6000,
    summarization_max_output=3000,
    tokens_per_second=80,
    description="Custom model"
))
```

---

## 📈 Рекомендации по настройке порога

### Формула для `summarization_threshold`

```python
summarization_threshold = effective_context_for_rag * 0.4

# Примеры:
# Llama 8B:  7180 * 0.4 = 2872 ≈ 3000
# Llama 70B: 15340 * 0.4 = 6136 ≈ 6000
# Mixtral:   31244 * 0.4 = 12498 ≈ 12000
```

**Почему 40%?**
- Оставляет буфер для prompt overhead
- Баланс между качеством и производительностью
- Проверено на практике

### Можно настроить по потребностям:

**Агрессивная суммаризация (30%):**
```json
"summarization_threshold": 2100  // для 8K context
```
- Чаще суммаризирует
- Экономит токены
- Быстрее ответы

**Консервативная (50%):**
```json
"summarization_threshold": 3600  // для 8K context
```
- Реже суммаризирует
- Больше деталей в контексте
- Лучше для сложных вопросов

---

## 🎉 Преимущества такого подхода

### 1. **Автоматическая адаптация**
```bash
# Переключение на модель с большим контекстом
LLM_MODEL=mistralai/Mixtral-8x7B-Instruct-v0.1

# Пайплайн автоматически:
# - Увеличивает порог суммаризации: 3K → 12K
# - Увеличивает max_output: 1.5K → 4K
# - Реже использует суммаризацию
```

### 2. **Нет hardcoded значений**
```python
# Плохо (старый подход):
if context_tokens > 4000:  # Hardcoded!

# Хорошо (новый подход):
if context_tokens > model_config.summarization_threshold:  # Адаптивно!
```

### 3. **Легко добавлять новые модели**
- Добавили в JSON → автоматически работает
- Не нужно менять код
- Централизованная конфигурация

### 4. **Прозрачность**
```bash
# Узнать параметры текущей модели
curl http://localhost:8000/model-config

# Увидеть порог суммаризации
# Понять почему сработала/не сработала суммаризация
```

---

## 📝 Итоговые изменения

### Создано:
1. ✅ `backend/services/llm_config.py` - реестр моделей
2. ✅ `config/llm_models.json` - конфигурация (10 моделей)
3. ✅ `GET /model-config` - endpoint для просмотра

### Обновлено:
1. ✅ `backend/app.py` - использует `model_config.summarization_threshold`
2. ✅ Response `/ask` теперь включает:
   - `summarized: true/false`
   - `context_tokens: число`
   - `model: имя модели`

---

## 🧪 Тестирование

### Проверить конфигурацию модели

```bash
# Узнать параметры текущей модели
curl http://localhost:8000/model-config | jq

# Ожидаемый ответ:
# {
#   "model_name": "llama3.1:8b",
#   "context_window": 8192,
#   "summarization_threshold": 3000,
#   ...
# }
```

### Тест авто-суммаризации

```bash
# Запрос с малым контекстом (не суммаризируется)
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"q":"What is the deadline?","space_id":"demo","top_k":3}' | jq '.summarized'
# → false

# Запрос с большим контекстом (суммаризируется)
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"q":"Tell me about all projects","space_id":"demo","top_k":20}' | jq '.summarized'
# → true
```

### Смена модели и повторный тест

```bash
# 1. Остановить
make down

# 2. Изменить модель в .env
echo "LLM_MODEL=mistralai/Mixtral-8x7B-Instruct-v0.1" >> .env

# 3. Запустить с vLLM
make up-vllm

# 4. Проверить новые параметры
curl http://localhost:8000/model-config | jq '.summarization_threshold'
# → 12000 (вместо 3000!)

# 5. Тот же запрос что раньше суммаризировался
curl -X POST http://localhost:8000/ask \
  -d '{"q":"Tell me about all projects","top_k":20}' | jq '.summarized'
# → false (теперь НЕ суммаризируется, т.к. 32K context!)
```

---

## 🎯 Готово к интеграции?

Хотите чтобы я встроил этот паттерн, или есть предложения по улучшению?

**Что получаем:**
- ✅ Адаптивная суммаризация под каждую модель
- ✅ Централизованная конфигурация
- ✅ Легко добавлять новые модели
- ✅ Прозрачность через `/model-config`
- ✅ Автоматическая оптимизация при смене модели

Скажите **"приступай"** или предложите изменения! 👍

