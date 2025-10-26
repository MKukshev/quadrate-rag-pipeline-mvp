# Абстрактные названия моделей - Справочник

Документация по использованию абстрактных названий вместо конкретных моделей.

## 🔄 Изменения в именовании

### Переменные окружения

| Старое название | Новое название | Описание |
|----------------|----------------|----------|
| `VLLM_MODEL_GPT` | `VLLM_MODEL_MEDIUM` | Большая модель (~13-20B параметров) |
| `VLLM_MODEL_MISTRAL` | `VLLM_MODEL_SMALL` | Меньшая модель (~7B параметров) |
| `VLLM_GPU_MEMORY_UTILIZATION_GPT` | `VLLM_GPU_MEMORY_UTILIZATION_MEDIUM` | Утилизация GPU для medium модели |
| `VLLM_GPU_MEMORY_UTILIZATION_MISTRAL` | `VLLM_GPU_MEMORY_UTILIZATION_SMALL` | Утилизация GPU для small модели |
| `VLLM_MAX_MODEL_LEN_GPT` | `VLLM_MAX_MODEL_LEN_MEDIUM` | Макс. длина контекста medium |
| `VLLM_MAX_MODEL_LEN_MISTRAL` | `VLLM_MAX_MODEL_LEN_SMALL` | Макс. длина контекста small |
| `VLLM_MAX_NUM_SEQS_GPT` | `VLLM_MAX_NUM_SEQS_MEDIUM` | Макс. sequences для medium |
| `VLLM_MAX_NUM_SEQS_MISTRAL` | `VLLM_MAX_NUM_SEQS_SMALL` | Макс. sequences для small |
| `MIG_2G_48GB` | `MIG_MEDIUM` | MIG устройство для medium модели |
| `MIG_1G_24GB_MISTRAL` | `MIG_SMALL` | MIG устройство для small модели |

### Docker контейнеры

| Старое название | Новое название | Порт |
|----------------|----------------|------|
| `vllm-gpt` / `vllm-gpt-20b` | `vllm-medium` | 8001 |
| `vllm-mistral` / `vllm-mistral-7b` | `vllm-small` | 8002 |

### Make команды

| Старое название | Новое название | Описание |
|----------------|----------------|----------|
| `make logs-gpt` | `make logs-medium` | Логи medium модели |
| `make logs-mistral` | `make logs-small` | Логи small модели |
| `make test-gpt` | `make test-medium` | Тест medium модели |
| `make test-mistral` | `make test-small` | Тест small модели |
| `make restart-gpt` | `make restart-medium` | Перезапуск medium |
| `make restart-mistral` | `make restart-small` | Перезапуск small |

## 📝 Настройка .env файла

> 🎯 **Важно**: Docker Compose теперь использует стандартный `.env` файл из корня проекта автоматически!

### Проверка конфигурации

```bash
# Проверить существующие переменные
make check-env

# Или вручную
cat .env | grep -E "VLLM_MODEL|MIG_"
```

### Пример .env файла

Создайте или обновите `.env` в корне проекта:

```bash
# ==================================================================
# HuggingFace Token
# ==================================================================
HF_TOKEN=your_huggingface_token_here

# ==================================================================
# MEDIUM Model Configuration (порт 8001)
# Примеры: OpenGPT/gpt-oss-20b, meta-llama/Llama-2-13b-chat-hf
# ==================================================================
VLLM_MODEL_MEDIUM=OpenGPT/gpt-oss-20b
VLLM_GPU_MEMORY_UTILIZATION_MEDIUM=0.85
VLLM_MAX_MODEL_LEN_MEDIUM=8192
VLLM_MAX_NUM_SEQS_MEDIUM=128

# ==================================================================
# SMALL Model Configuration (порт 8002)
# Примеры: mistralai/Mistral-7B-Instruct-v0.3, meta-llama/Llama-2-7b-chat-hf
# ==================================================================
VLLM_MODEL_SMALL=mistralai/Mistral-7B-Instruct-v0.3
VLLM_GPU_MEMORY_UTILIZATION_SMALL=0.90
VLLM_MAX_MODEL_LEN_SMALL=16384
VLLM_MAX_NUM_SEQS_SMALL=256

# ==================================================================
# MIG Device IDs
# ==================================================================
MIG_MEDIUM=MIG-GPU-xxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/7/0
MIG_SMALL=MIG-GPU-xxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/14/0
MIG_1G_24GB=MIG-GPU-xxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/15/0
```

## 🚀 Быстрые команды

### Управление контейнерами

```bash
# Запуск обеих моделей
make up-dual-models

# Остановка
make down-dual-models

# Просмотр логов
make logs-medium      # только MEDIUM
make logs-small       # только SMALL
make logs-dual-models # обе сразу

# Перезапуск
make restart-medium
make restart-small

# Тестирование
make test-medium
make test-small
make test-both-models
make test-dual-models  # полный тест-сьют
```

### Docker команды напрямую

```bash
# Запуск
docker-compose -f docker-compose.vllm-mig.yml up -d

# Логи
docker logs -f vllm-medium
docker logs -f vllm-small

# Перезапуск
docker-compose -f docker-compose.vllm-mig.yml restart vllm-medium
docker-compose -f docker-compose.vllm-mig.yml restart vllm-small
```

## 🔧 Настройка AnythingLLM

### MEDIUM model (порт 8001)

```
LLM Provider: Generic OpenAI
Base URL: http://localhost:8001/v1
API Key: not-needed
Model Name: <значение из VLLM_MODEL_MEDIUM>
```

### SMALL model (порт 8002)

```
LLM Provider: Generic OpenAI
Base URL: http://localhost:8002/v1
API Key: not-needed
Model Name: <значение из VLLM_MODEL_SMALL>
```

## 💡 Примеры моделей

### Для MEDIUM model (обычно 2g.48gb MIG, ~40-45 GB памяти)

- `OpenGPT/gpt-oss-20b` - 20B параметров, хорошие общие возможности
- `meta-llama/Llama-2-13b-chat-hf` - 13B параметров, чат-оптимизированная
- `mistralai/Mixtral-8x7B-Instruct-v0.1` - MoE модель, высокая производительность
- `upstage/SOLAR-10.7B-Instruct-v1.0` - 11B параметров, эффективная

### Для SMALL model (обычно 1g.24gb MIG, ~14-16 GB памяти)

- `mistralai/Mistral-7B-Instruct-v0.3` - 7B параметров, отличная для кода
- `meta-llama/Llama-2-7b-chat-hf` - 7B параметров, чат-оптимизированная
- `teknium/OpenHermes-2.5-Mistral-7B` - 7B параметров, хорошо следует инструкциям
- `NousResearch/Nous-Hermes-2-Mixtral-8x7B-DPO` - MoE, высокая производительность

## 📊 Сравнение использования

### MEDIUM model (порт 8001)
- **Размер**: обычно 13-20+ B параметров
- **Память**: ~40-45 GB на 2g.48gb MIG
- **Скорость**: ~30-50 tokens/sec
- **Latency**: ~500-800ms (первый токен)
- **Применение**: Сложный анализ, длинные документы, детальные ответы

### SMALL model (порт 8002)
- **Размер**: обычно 7B параметров
- **Память**: ~14-16 GB на 1g.24gb MIG
- **Скорость**: ~80-120 tokens/sec
- **Latency**: ~200-400ms (первый токен)
- **Применение**: Быстрые ответы, генерация кода, простые задачи

## 🔍 Проверка конфигурации

```bash
# Проверить health обеих моделей
curl http://localhost:8001/health
curl http://localhost:8002/health

# Посмотреть какие модели загружены
curl http://localhost:8001/v1/models | jq '.data[0].id'
curl http://localhost:8002/v1/models | jq '.data[0].id'

# Мониторинг GPU
nvidia-smi

# Детальная информация о MIG
nvidia-smi mig -lgi
```

## 📚 Обновлённая документация

Следующие файлы были обновлены с новым именованием:

- ✅ `docker-compose.vllm-mig.yml` - Основная конфигурация
- ✅ `Makefile` - Make команды и таргеты
- ✅ `DUAL_MODELS_QUICKSTART.md` - Полное руководство по dual models
- ✅ `ANYTHINGLLM_INTEGRATION.md` - Интеграция с AnythingLLM
- ✅ `scripts/test_dual_models.sh` - Тестовый скрипт

## ⚠️ Миграция с старого именования

Если у вас уже есть `.env` файл со старыми переменными, обновите их:

```bash
# Было:
VLLM_MODEL_GPT=OpenGPT/gpt-oss-20b
VLLM_MODEL_MISTRAL=mistralai/Mistral-7B-Instruct-v0.3
MIG_2G_48GB=MIG-GPU-xxxxx.../7/0
MIG_1G_24GB_MISTRAL=MIG-GPU-xxxxx.../14/0

# Стало:
VLLM_MODEL_MEDIUM=OpenGPT/gpt-oss-20b
VLLM_MODEL_SMALL=mistralai/Mistral-7B-Instruct-v0.3
MIG_MEDIUM=MIG-GPU-xxxxx.../7/0
MIG_SMALL=MIG-GPU-xxxxx.../14/0
```

После обновления переменных:

```bash
# Пересоздайте контейнеры
docker-compose -f docker-compose.vllm-mig.yml down
make up-dual-models

# Или используя docker-compose напрямую
docker-compose --env-file .env.vllm-dual-models -f docker-compose.vllm-mig.yml up -d --force-recreate
```

## ❓ FAQ

**Q: Почему переименовали?**
A: Чтобы сделать конфигурацию более гибкой и не привязываться к конкретным моделям. Теперь вы можете легко менять модели без изменения кода и документации.

**Q: Могу ли я использовать другие модели?**
A: Да! Просто укажите любую совместимую с vLLM модель из HuggingFace в переменных `VLLM_MODEL_MEDIUM` и `VLLM_MODEL_SMALL`.

**Q: Нужно ли обновлять старые контейнеры?**
A: Да, после изменения переменных окружения пересоздайте контейнеры с `--force-recreate` флагом.

**Q: Можно ли использовать две модели одинакового размера?**
A: Да, названия MEDIUM и SMALL - это просто условное обозначение для двух слотов. Вы можете запустить любые две модели.


