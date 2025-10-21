# LLM Конфигурация - Подробное объяснение

## 🤔 Зачем две переменные для модели?

### Краткий ответ
- **`LLM_MODEL`** - для Backend (Python)
- **`VLLM_MODEL`** - для vLLM Container

**Должны быть одинаковыми при использовании vLLM!**

---

## 📊 Архитектура: Backend + vLLM

```
┌─────────────────────────────────────────────────────────────┐
│  docker-compose.yml / docker-compose.vllm.yml               │
│                                                             │
│  ┌──────────────────────┐      ┌───────────────────────┐  │
│  │  Backend Container   │      │   vLLM Container      │  │
│  │  (FastAPI)           │      │   (Model Server)      │  │
│  │                      │      │                       │  │
│  │  LLM_MODE=vllm ◄─────┼──────┼─── Какой провайдер   │  │
│  │  LLM_MODEL=llama... ◄┼──────┼─── Для логов/метрик  │  │
│  │  LLM_VLLM_URL=... ◄──┼──────┼─── Где vLLM сервер   │  │
│  │                      │      │                       │  │
│  │                      │ HTTP │   VLLM_MODEL=llama... │  │
│  │  call_vllm(prompt)──┼──────┼──►Загружает эту модель│  │
│  │                      │      │   VLLM_GPU_MEM=0.95   │  │
│  │                      │      │   VLLM_MAX_LEN=16K    │  │
│  └──────────────────────┘      └───────────────────────┘  │
│           Port 8000                     Port 8001          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔑 Ключевые переменные

### 1. Переменные уровня приложения (Backend)

```python
# backend/services/config.py
LLM_MODE = "vllm"           # Какой провайдер использовать
LLM_MODEL = "meta-llama..." # Какую модель (для метрик/логов)
LLM_VLLM_URL = "http://..."# Где находится vLLM API
LLM_TIMEOUT = 120           # Таймаут запроса
LLM_MAX_TOKENS = 512        # Макс токенов в ответе
```

**Используются в:**
- `backend/services/rag.py` - для выбора провайдера
- `backend/app.py` - для health check
- Логи и метрики

### 2. Переменные уровня контейнера (vLLM)

```bash
# docker-compose.vllm.yml
VLLM_MODEL=meta-llama/...           # Какую модель загрузить
VLLM_GPU_MEMORY_UTILIZATION=0.95   # Сколько GPU памяти
VLLM_MAX_MODEL_LEN=16384            # Длина контекста
VLLM_TENSOR_PARALLEL_SIZE=1         # Кол-во GPU
VLLM_ENABLE_FP8=true                # FP8 precision
```

**Используются в:**
- vLLM container при запуске
- Загрузка модели из HuggingFace
- Конфигурация GPU

---

## 💡 Почему не одна переменная?

### Попытка использовать только LLM_MODEL

```bash
# Если использовать только LLM_MODEL
LLM_MODEL=llama3.1:8b

# Проблемы:
# 1. Backend отправит "llama3.1:8b" в vLLM
# 2. vLLM попытается загрузить "llama3.1:8b" из HuggingFace
# 3. Ошибка: модель не найдена (это Ollama формат, не HF!)
```

### Попытка автоматически конвертировать

```python
# Теоретически можно:
if LLM_MODE == "vllm":
    # Конвертировать Ollama формат в HF
    if LLM_MODEL == "llama3.1:8b":
        vllm_model = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    elif LLM_MODEL == "mistral:7b":
        vllm_model = "mistralai/Mistral-7B-Instruct-v0.2"
    # ...

# ❌ Проблема: слишком много вариантов, легко сломать
```

---

## ✅ Рекомендуемый подход

### Вариант A: Синхронизация в .env (текущий)

```bash
# .env.vllm
LLM_MODE=vllm
LLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
VLLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
```

**Преимущества:**
- ✅ Явная конфигурация
- ✅ Полный контроль
- ✅ Нет магии

**Недостатки:**
- ❌ Нужно синхронизировать вручную

### Вариант B: VLLM_MODEL по умолчанию = LLM_MODEL

```bash
# .env.vllm (упрощенный)
LLM_MODE=vllm
LLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
# VLLM_MODEL не указан, автоматически = LLM_MODEL
```

**Реализация в docker-compose.vllm.yml:**
```yaml
environment:
  - VLLM_MODEL=${VLLM_MODEL:-${LLM_MODEL}}
```

**Преимущества:**
- ✅ Меньше дублирования
- ✅ Легче использовать

**Недостатки:**
- ❌ Нужна поддержка в docker-compose

---

## 📝 Текущее состояние (после обновления)

### В ваших .env файлах:

#### `.env.ollama`
```bash
LLM_MODE=ollama
LLM_MODEL=llama3.1:8b
# VLLM_MODEL не нужна
```

#### `.env.vllm`
```bash
LLM_MODE=vllm
LLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct  # ← Backend
VLLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct # ← vLLM
# Обе переменные нужны и должны совпадать!
```

#### `.env.vllm-fp8`
```bash
LLM_MODE=vllm
LLM_MODEL=neuralmagic/Meta-Llama-3.1-70B-Instruct-FP8  # ← Backend
VLLM_MODEL=neuralmagic/Meta-Llama-3.1-70B-Instruct-FP8 # ← vLLM
```

---

## 🎯 Рекомендация

### Для упрощения использования

Я рекомендую **оставить как есть** (две переменные), потому что:

1. **Явность лучше неявности** - сразу видно что настраивается
2. **Гибкость** - можно указать разные значения если нужно
3. **Debugging** - легче найти проблему конфигурации
4. **Документация** - проще объяснить что куда идёт

### Но добавить валидацию

В `backend/services/rag_vllm.py` можно добавить проверку:

```python
def call_vllm(prompt: str, model: Optional[str] = None, **kwargs) -> str:
    model = model or config.LLM_MODEL
    
    # Валидация: проверить что модель совпадает с VLLM_MODEL
    vllm_model = os.getenv("VLLM_MODEL")
    if vllm_model and model != vllm_model:
        logger.warning(
            f"LLM_MODEL ({model}) != VLLM_MODEL ({vllm_model}). "
            f"Using {model} for API call."
        )
    
    # ... остальной код
```

---

## 📚 См. также

- [VLLM_QUICKSTART.md](../VLLM_QUICKSTART.md) - быстрый старт
- [docs/VLLM_DEPLOYMENT.md](VLLM_DEPLOYMENT.md) - развертывание
- [docs/BLACKWELL_OPTIMIZATIONS.md](BLACKWELL_OPTIMIZATIONS.md) - оптимизации

