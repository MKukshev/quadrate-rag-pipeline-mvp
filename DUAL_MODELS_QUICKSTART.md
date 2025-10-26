# Dual vLLM Models Configuration Guide

Руководство по одновременному запуску двух моделей vLLM с использованием NVIDIA MIG.

## 📋 Обзор архитектуры

```
┌─────────────────────────────────────────────────────────────┐
│                      NVIDIA GPU (96GB)                       │
│                     MIG Partitioning                         │
├─────────────────┬─────────────────┬─────────────────────────┤
│  2g.48gb MIG    │  1g.24gb MIG    │    1g.24gb MIG          │
│  (MEDIUM model) │  (SMALL model)  │    (Backend/Embed)      │
│  Port: 8001     │  Port: 8002     │    Port: 8000           │
└─────────────────┴─────────────────┴─────────────────────────┘
         │                 │                      │
         │                 │                      │
    http://localhost:8001/v1  http://localhost:8002/v1
         │                 │                      │
         └─────────────────┴──────────────────────┘
                           │
                    AnythingLLM / Applications
```

## 🚀 Быстрый старт

### 1. Настройка MIG устройств

Получите список доступных MIG устройств:

```bash
nvidia-smi -L
# или используйте наш скрипт
bash scripts/list_mig_devices.sh
```

Пример вывода:
```
GPU 0: NVIDIA RTX 6000 Ada Generation
  MIG 2g.48gb Device 0: (UUID: MIG-GPU-xxxxx.../7/0)
  MIG 1g.24gb Device 1: (UUID: MIG-GPU-xxxxx.../14/0)
  MIG 1g.24gb Device 2: (UUID: MIG-GPU-xxxxx.../15/0)
```

### 2. Создание .env файла

Создайте или обновите файл `.env` в корне проекта с вашими переменными:

> 💡 **Совет**: Docker Compose автоматически загружает `.env` файл. См. подробности в `ENV_SETUP_GUIDE.md`

```bash
# ==================================================================
# HuggingFace Token
# ==================================================================
HF_TOKEN=your_huggingface_token_here

# ==================================================================
# MEDIUM Model Configuration (большая модель, порт 8001)
# Пример: OpenGPT/gpt-oss-20b, meta-llama/Llama-2-13b-chat-hf
# ==================================================================
VLLM_MODEL_MEDIUM=OpenGPT/gpt-oss-20b
VLLM_GPU_MEMORY_UTILIZATION_MEDIUM=0.85
VLLM_MAX_MODEL_LEN_MEDIUM=8192
VLLM_MAX_NUM_SEQS_MEDIUM=128

# ==================================================================
# SMALL Model Configuration (меньшая модель, порт 8002)
# Пример: mistralai/Mistral-7B-Instruct-v0.3, meta-llama/Llama-2-7b-chat-hf
# ==================================================================
VLLM_MODEL_SMALL=mistralai/Mistral-7B-Instruct-v0.3
VLLM_GPU_MEMORY_UTILIZATION_SMALL=0.90
VLLM_MAX_MODEL_LEN_SMALL=16384
VLLM_MAX_NUM_SEQS_SMALL=256

# ==================================================================
# MIG Device IDs
# ==================================================================
# MEDIUM model на 2g.48gb инстансе
MIG_MEDIUM=MIG-GPU-xxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/7/0

# SMALL model на 1g.24gb инстансе
MIG_SMALL=MIG-GPU-xxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/14/0

# Backend embeddings на отдельном 1g.24gb инстансе
MIG_1G_24GB=MIG-GPU-xxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/15/0
```

### 3. Проверка конфигурации

```bash
# Проверьте переменные окружения
make check-env
```

### 4. Запуск сервисов

```bash
# Запуск (автоматически использует .env файл из корня проекта)
make up-dual-models

# Или напрямую через docker-compose
docker-compose -f docker-compose.vllm-mig.yml up -d
```

> 💡 **Важно**: Убедитесь что `.env` файл находится в корне проекта. Docker Compose загрузит его автоматически.

### 5. Проверка работоспособности

```bash
# Проверка MEDIUM model (порт 8001)
curl http://localhost:8001/health
curl http://localhost:8001/v1/models

# Проверка SMALL model (порт 8002)
curl http://localhost:8002/health
curl http://localhost:8002/v1/models

# Проверка Qdrant
curl http://localhost:6333/healthz

# Проверка Backend
curl http://localhost:8000/health
```

## 🔧 Конфигурация AnythingLLM

### Вариант 1: Использовать MEDIUM model (мощнее, медленнее)

```
LLM Provider: Generic OpenAI
Base URL: http://localhost:8001/v1
API Key: not-needed
Model Name: <your-medium-model-name>
```

Примеры: `OpenGPT/gpt-oss-20b`, `meta-llama/Llama-2-13b-chat-hf`

### Вариант 2: Использовать SMALL model (быстрее, экономичнее)

```
LLM Provider: Generic OpenAI
Base URL: http://localhost:8002/v1
API Key: not-needed
Model Name: <your-small-model-name>
```

Примеры: `mistralai/Mistral-7B-Instruct-v0.3`, `meta-llama/Llama-2-7b-chat-hf`

### Переключение между моделями

AnythingLLM позволяет сохранить несколько LLM провайдеров и переключаться между ними:

1. Добавьте оба провайдера в настройках
2. Дайте им разные имена (например, "Medium Model" и "Small Model")
3. Переключайтесь в зависимости от задачи

## 📊 Тестирование моделей

### Тест MEDIUM model

```bash
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "<your-medium-model-name>",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Explain quantum computing in simple terms."}
    ],
    "temperature": 0.7,
    "max_tokens": 200
  }'
```

### Тест SMALL model

```bash
curl -X POST http://localhost:8002/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "<your-small-model-name>",
    "messages": [
      {"role": "user", "content": "Write a Python function to calculate fibonacci numbers."}
    ],
    "temperature": 0.7,
    "max_tokens": 200
  }'
```

## 🎯 Рекомендации по использованию

### MEDIUM model (порт 8001)
- ✅ Лучше для сложных рассуждений
- ✅ Лучше для длинных контекстов
- ✅ Более качественные ответы
- ❌ Медленнее генерация
- ❌ Требует больше памяти

**Рекомендуется для:**
- Аналитических задач
- Работы с большими документами
- Сложных инструкций

### SMALL model (порт 8002)
- ✅ Быстрая генерация
- ✅ Меньше памяти
- ✅ Хорошо для кода и простых задач
- ❌ Менее детальные ответы на сложные вопросы

**Рекомендуется для:**
- Быстрых ответов
- Генерации кода
- Простых вопросов
- Высокой пропускной способности

## 🔍 Мониторинг

### Просмотр логов

```bash
# Все сервисы
docker-compose -f docker-compose.vllm-mig.yml logs -f

# Только MEDIUM model
docker logs -f vllm-medium

# Только SMALL model
docker logs -f vllm-small

# Используя Make
make logs-medium
make logs-small
make logs-dual-models  # оба сразу
```

### Мониторинг GPU

```bash
# Использование памяти всех MIG устройств
nvidia-smi

# Детальная информация о MIG
nvidia-smi mig -lgi
nvidia-smi mig -lci

# Watch режим
watch -n 1 nvidia-smi
```

## ⚙️ Параметры настройки

### GPU Memory Utilization

```bash
# MEDIUM model (обычно большая модель ~20B параметров)
VLLM_GPU_MEMORY_UTILIZATION_MEDIUM=0.85  # 85% от 48GB = ~40GB

# SMALL model (обычно меньшая модель ~7B параметров)
VLLM_GPU_MEMORY_UTILIZATION_SMALL=0.90  # 90% от 24GB = ~21GB
```

### Max Model Length (контекстное окно)

```bash
# MEDIUM model
VLLM_MAX_MODEL_LEN_MEDIUM=8192  # 8K токенов (настраивается по модели)

# SMALL model
VLLM_MAX_MODEL_LEN_SMALL=16384  # 16K токенов (некоторые модели поддерживают больше)
```

### Max Num Sequences (batch size)

```bash
# MEDIUM model (меньше из-за размера модели)
VLLM_MAX_NUM_SEQS_MEDIUM=128

# SMALL model (больше, т.к. модель меньше)
VLLM_MAX_NUM_SEQS_SMALL=256
```

## 🐛 Troubleshooting

### Проблема: Out of Memory (OOM)

**Решение:**
1. Уменьшите `VLLM_GPU_MEMORY_UTILIZATION`
2. Уменьшите `VLLM_MAX_MODEL_LEN`
3. Уменьшите `VLLM_MAX_NUM_SEQS`

```bash
# Для MEDIUM model
VLLM_GPU_MEMORY_UTILIZATION_MEDIUM=0.80  # было 0.85
VLLM_MAX_MODEL_LEN_MEDIUM=4096          # было 8192

# Для SMALL model
VLLM_GPU_MEMORY_UTILIZATION_SMALL=0.85  # было 0.90
```

### Проблема: Модель не загружается

**Проверьте:**
1. Правильность MIG UUID в `.env` файле
2. Доступность HuggingFace токена
3. Наличие места на диске для кэша моделей

```bash
# Проверка MIG устройств
nvidia-smi -L

# Проверка логов
docker logs vllm-medium
docker logs vllm-small

# Используя Make
make logs-medium
make logs-small
```

### Проблема: Медленная генерация

**Оптимизация:**
1. Увеличьте `VLLM_MAX_NUM_SEQS` (если есть память)
2. Включите `VLLM_ENABLE_CHUNKED_PREFILL=true`
3. Используйте меньшую модель для простых задач

## 📈 Производительность

### Примерные показатели

| Модель | Tokens/sec | Latency (first token) | Memory Usage |
|--------|------------|----------------------|--------------|
| MEDIUM (~20B) | ~30-50 | ~500-800ms | ~40-45 GB |
| SMALL (~7B) | ~80-120 | ~200-400ms | ~14-16 GB |

*Зависит от конкретной модели, длины контекста и параметров

## 🔄 Управление сервисами

```bash
# Запуск
docker-compose -f docker-compose.vllm-mig.yml up -d

# Остановка
docker-compose -f docker-compose.vllm-mig.yml down

# Перезапуск конкретного сервиса
docker-compose -f docker-compose.vllm-mig.yml restart vllm-medium
docker-compose -f docker-compose.vllm-mig.yml restart vllm-small

# Используя Make
make restart-medium
make restart-small

# Обновление после изменения конфигурации
docker-compose -f docker-compose.vllm-mig.yml up -d --force-recreate
```

## 📚 Дополнительные ресурсы

- [vLLM Documentation](https://docs.vllm.ai/)
- [NVIDIA MIG User Guide](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/)
- [HuggingFace Models](https://huggingface.co/models)

## ❓ FAQ

**Q: Можно ли запустить больше двух моделей?**
A: Да, добавьте дополнительные сервисы в `docker-compose.vllm-mig.yml` с уникальными портами и MIG устройствами.

**Q: Какие модели можно использовать?**
A: Любые модели из HuggingFace, совместимые с vLLM. Примеры:
- MEDIUM: OpenGPT/gpt-oss-20b, meta-llama/Llama-2-13b-chat-hf, mistralai/Mixtral-8x7B-Instruct-v0.1
- SMALL: mistralai/Mistral-7B-Instruct-v0.3, meta-llama/Llama-2-7b-chat-hf, teknium/OpenHermes-2.5-Mistral-7B

**Q: Можно ли использовать одно MIG устройство для двух моделей?**
A: Нет, каждая модель должна иметь свой выделенный MIG инстанс.

**Q: Как изменить модель на лету?**
A: Обновите переменную `VLLM_MODEL_MEDIUM` или `VLLM_MODEL_SMALL` в `.env` файле и пересоздайте контейнер:
```bash
docker-compose -f docker-compose.vllm-mig.yml up -d --force-recreate vllm-medium
# или
make restart-medium
```

