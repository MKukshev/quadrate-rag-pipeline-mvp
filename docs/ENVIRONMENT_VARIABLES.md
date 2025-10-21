# Переменные окружения - Полный справочник

## 🎯 LLM Провайдер (Backend)

### `LLM_MODE`
**Назначение:** Выбор LLM провайдера  
**Используется в:** Backend (Python)  
**Значения:**
- `ollama` - использовать Ollama (по умолчанию)
- `vllm` - использовать vLLM
- `none` - отключить LLM (только поиск)

**Пример:**
```bash
LLM_MODE=vllm  # Переключение на vLLM
```

---

## 📦 LLM Модель

### ⚠️ Важно: Две переменные для модели

#### `LLM_MODEL` (Backend)
**Назначение:** Имя модели для backend логики  
**Используется в:** 
- Backend Python код
- Логирование
- Метрики
- API responses

**Формат:** Может быть любой строкой  
**Примеры:**
```bash
# Ollama
LLM_MODEL=llama3.1:8b

# vLLM
LLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
```

#### `VLLM_MODEL` (vLLM Container)
**Назначение:** Имя модели для загрузки в vLLM  
**Используется в:** vLLM сервис (отдельный контейнер)  
**Формат:** HuggingFace model ID  
**Примеры:**
```bash
VLLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
VLLM_MODEL=neuralmagic/Meta-Llama-3.1-70B-Instruct-FP8
VLLM_MODEL=mistralai/Mixtral-8x7B-Instruct-v0.1
```

### 🔗 Синхронизация LLM_MODEL и VLLM_MODEL

**Правило:** При использовании vLLM, `LLM_MODEL` и `VLLM_MODEL` должны быть одинаковыми!

#### ✅ Правильно:
```bash
LLM_MODE=vllm
LLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
VLLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
```

#### ❌ Неправильно:
```bash
LLM_MODE=vllm
LLM_MODEL=llama3.1:8b                                    # ← Ollama формат
VLLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct       # ← HF формат
# Backend думает что модель llama3.1:8b, но vLLM загружает другую!
```

---

## 🔧 Почему две переменные?

### Архитектурная причина

```
┌──────────────────────────────────────┐
│  Backend Container                   │
│                                      │
│  - Читает LLM_MODE                  │
│  - Использует LLM_MODEL             │
│  - Отправляет запросы к vLLM        │
└──────────────────────────────────────┘
                 │
                 │ HTTP Request
                 ▼
┌──────────────────────────────────────┐
│  vLLM Container                      │
│                                      │
│  - Читает VLLM_MODEL                │
│  - Загружает модель из HuggingFace  │
│  - Запускает vLLM сервер            │
└──────────────────────────────────────┘
```

**Разделение:**
- Backend не знает деталей vLLM
- vLLM не знает о backend
- Каждый контейнер независим

### Историческая причина

Изначально была только одна переменная `LLM_MODEL` для Ollama:
```bash
LLM_MODEL=llama3.1:8b  # Ollama формат
```

При добавлении vLLM понадобилась отдельная переменная:
```bash
VLLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct  # HF формат
```

---

## 📋 Примеры конфигураций

### Конфигурация 1: Ollama
```bash
LLM_MODE=ollama
LLM_MODEL=llama3.1:8b
# VLLM_MODEL не используется
```

### Конфигурация 2: vLLM (Llama-8B)
```bash
LLM_MODE=vllm
LLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
VLLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
```

### Конфигурация 3: vLLM (Llama-70B FP8)
```bash
LLM_MODE=vllm
LLM_MODEL=neuralmagic/Meta-Llama-3.1-70B-Instruct-FP8
VLLM_MODEL=neuralmagic/Meta-Llama-3.1-70B-Instruct-FP8
```

### Конфигурация 4: Без LLM
```bash
LLM_MODE=none
# LLM_MODEL и VLLM_MODEL игнорируются
```

---

## 🔄 Упрощение (Рекомендация)

### Проблема дублирования

Текущая конфигурация требует дублирования:
```bash
LLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct     # 1-й раз
VLLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct   # 2-й раз
```

### Решение: Использовать одну переменную

В backend/services/config.py можно добавить:
```python
LLM_MODE = os.getenv("LLM_MODE", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")

# Для vLLM используем LLM_MODEL если VLLM_MODEL не указан
VLLM_MODEL = os.getenv("VLLM_MODEL", LLM_MODEL if LLM_MODE == "vllm" else "")
```

Тогда в .env достаточно:
```bash
LLM_MODE=vllm
LLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
# VLLM_MODEL автоматически = LLM_MODEL
```

---

## 📊 Полный список LLM переменных

| Переменная | Контейнер | Обязательная | Описание |
|-----------|-----------|--------------|----------|
| `LLM_MODE` | Backend | ✅ | Провайдер: ollama/vllm/none |
| `LLM_MODEL` | Backend | ✅ | Имя модели (общее) |
| `LLM_TIMEOUT` | Backend | ❌ | Таймаут запроса (сек) |
| `LLM_MAX_TOKENS` | Backend | ❌ | Макс токенов ответа |
| `LLM_TEMPERATURE` | Backend | ❌ | Temperature (0.0-1.0) |
| `LLM_STREAM_ENABLED` | Backend | ❌ | Streaming ответа |
| `LLM_VLLM_URL` | Backend | ✅* | URL vLLM API (если LLM_MODE=vllm) |
| `VLLM_MODEL` | vLLM | ✅* | Модель для vLLM (если используется) |
| `VLLM_GPU_MEMORY_UTILIZATION` | vLLM | ❌ | GPU memory (0.0-1.0) |
| `VLLM_MAX_MODEL_LEN` | vLLM | ❌ | Макс длина контекста |
| `VLLM_TENSOR_PARALLEL_SIZE` | vLLM | ❌ | Кол-во GPU |
| `VLLM_ENABLE_FP8` | vLLM | ❌ | FP8 precision |
| `VLLM_USE_FLASHINFER` | vLLM | ❌ | FlashInfer attention |

\* - обязательна при соответствующем режиме

---

## 🎯 Quick Reference

### Я хочу использовать Ollama
```bash
LLM_MODE=ollama
LLM_MODEL=llama3.1:8b
```

### Я хочу использовать vLLM
```bash
LLM_MODE=vllm
LLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
VLLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
LLM_VLLM_URL=http://vllm:8001/v1
```

### Я хочу отключить LLM (только поиск)
```bash
LLM_MODE=none
```

### Я хочу сменить модель в vLLM
```bash
# 1. Остановить
make down-vllm

# 2. Обновить обе переменные
nano .env
# LLM_MODEL=новая-модель
# VLLM_MODEL=новая-модель

# 3. Запустить
make up-vllm
```

---

## 🐛 Troubleshooting

### Ошибка: "Model not found"
**Причина:** `VLLM_MODEL` не синхронизирован с `LLM_MODEL`  
**Решение:** Проверьте что обе переменные одинаковые

### Ошибка: "Connection refused"
**Причина:** `LLM_VLLM_URL` неправильный  
**Решение:** Должно быть `http://vllm:8001/v1`

### Backend показывает неправильную модель
**Причина:** `LLM_MODEL` отличается от `VLLM_MODEL`  
**Решение:** Синхронизируйте переменные

