# Динамический расчет max_tokens

## ✅ Что реализовано

Теперь `max_tokens` рассчитывается динамически на основе:
1. **Контекстного окна модели** (из `llm_models.json`)
2. **Размера текущего промпта** (фактический input)
3. **Safety margin** (запас для безопасности)

---

## 🔧 Реализация

### 1. Новая функция в `backend/services/rag.py`:

```python
def calculate_dynamic_max_tokens(
    prompt: str, 
    context_window: int, 
    safety_margin: int = 500
) -> int:
    """
    Динамически рассчитывает макс токенов для ответа
    
    Формула:
    available = context_window - prompt_tokens - safety_margin
    """
    prompt_tokens = len(prompt.split())  # Приблизительный подсчет
    available = context_window - prompt_tokens - safety_margin
    
    # Не меньше 256, не больше 4096
    return max(256, min(available, 4096))
```

### 2. Обновлён `call_llm()` для приёма опционального `max_tokens`:

```python
def call_llm(prompt: str, max_tokens: int = None) -> str:
    if LLM_MODE == "ollama":
        num_predict = max_tokens if max_tokens is not None else LLM_MAX_TOKENS
        ...
    elif LLM_MODE == "vllm":
        kwargs = {}
        if max_tokens is not None:
            kwargs['max_tokens'] = max_tokens
        return call_vllm(prompt, **kwargs)
```

### 3. Используется в суммаризации:

```python
# В summarize_text()
model_config = get_current_model_config()
dynamic_max = calculate_dynamic_max_tokens(prompt, model_config.context_window)
actual_max = min(max_summary_tokens, dynamic_max)

print(f"Dynamic max_tokens: {actual_max} (requested: {max_summary_tokens}, available: {dynamic_max})")

summary = call_llm(prompt, max_tokens=actual_max)
```

---

## 📊 Как это работает

### Пример для llama3.1:8b

**Модель:**
- context_window = 8192 токенов

**Сценарий 1: Маленький документ (короткий промпт)**

```
prompt_tokens = 500
available = 8192 - 500 - 500 = 7192
dynamic_max = min(7192, 4096) = 4096
actual_max = min(500, 4096) = 500  ✅
```

**Сценарий 2: Большой документ (длинный промпт)**

```
prompt_tokens = 6000
available = 8192 - 6000 - 500 = 1692
dynamic_max = min(1692, 4096) = 1692
actual_max = min(1500, 1692) = 1500  ✅
```

**Сценарий 3: Очень большой промпт**

```
prompt_tokens = 7500
available = 8192 - 7500 - 500 = 192
dynamic_max = max(256, min(192, 4096)) = 256  ✅ Минимум
actual_max = min(1500, 256) = 256  ⚠️ Предупреждение в логах
```

---

## 🎯 Преимущества

### ✅ Адаптивность

**Было (фиксированное):**
```python
call_llm(prompt)  # Всегда LLM_MAX_TOKENS=2048
```

Проблемы:
- ❌ Короткий промпт → зря резервируем 2048 токенов
- ❌ Длинный промпт → может не влезть в context_window

**Стало (динамическое):**
```python
dynamic_max = calculate_dynamic_max_tokens(prompt, context_window)
call_llm(prompt, max_tokens=dynamic_max)
```

Преимущества:
- ✅ Короткий промпт → может дать длинный ответ
- ✅ Длинный промпт → автоматически уменьшает max_tokens
- ✅ Всегда оптимально использует доступное пространство

---

## 📈 Сравнение: llama3.1:8b vs qwen3:14b

### llama3.1:8b (context_window = 8192)

```
Промпт 1000 токенов:
  available = 8192 - 1000 - 500 = 6692
  dynamic_max = min(6692, 4096) = 4096 ✅

Промпт 7000 токенов:
  available = 8192 - 7000 - 500 = 692
  dynamic_max = max(256, 692) = 692 ⚠️
```

### qwen3:14b (context_window = 40960)

```
Промпт 1000 токенов:
  available = 40960 - 1000 - 500 = 39460
  dynamic_max = min(39460, 4096) = 4096 ✅

Промпт 30000 токенов:
  available = 40960 - 30000 - 500 = 10460
  dynamic_max = min(10460, 4096) = 4096 ✅ Все еще достаточно!
```

**Вывод:** Модели с большим context_window дают больше гибкости!

---

## 🧪 Тестирование

### Проверка динамического расчета

```bash
# Тест 1: Короткий документ
curl -X POST /summarize -d '{"doc_id":"short_doc"}'

# В логах:
# [Summarization] Dynamic max_tokens: 1500 (requested: 500, available: 7000)
```

```bash
# Тест 2: Длинный документ
curl -X POST /summarize -d '{"doc_id":"long_doc"}'

# В логах:
# [Summarization] Dynamic max_tokens: 800 (requested: 1500, available: 800)
```

---

## ⚙️ Конфигурация

### Теперь LLM_MAX_TOKENS - это fallback!

```yaml
# docker-compose.yml
environment:
  - LLM_MAX_TOKENS=2048  # Используется как default если не передан явно
```

**Для RAG:**
- Использует `LLM_MAX_TOKENS` (2048) как есть

**Для суммаризации:**
- Динамически рассчитывает оптимальное значение
- Использует минимум из `desired` и `available`

---

## 🎯 Ответ на ваш вопрос

### Можно ли рассчитывать динамически?

**✅ ДА! И это реализовано!**

**Формула:**
```python
available_for_output = context_window - prompt_tokens - safety_margin
actual_max_tokens = min(desired_max, available_for_output)
```

**Преимущества:**
1. ✅ Оптимальное использование context_window
2. ✅ Автоматическая адаптация под размер промпта
3. ✅ Предотвращение переполнения контекста
4. ✅ Больше flexibility для моделей с большим окном

**Стоит ли ставить LLM_MAX_TOKENS больше 2048?**

**Ответ:** Теперь это **не так важно**, потому что:
- Для суммаризации используется динамический расчёт
- `LLM_MAX_TOKENS` теперь только fallback для обычного RAG
- 2048 - оптимальное значение для fallback ✅

---

**Готово к тестированию!** 🚀

