# Environment Setup Guide

Руководство по настройке переменных окружения для `docker-compose.vllm-mig.yml`.

## 🎯 Быстрая настройка

Docker Compose автоматически загружает файл `.env` из корня проекта. Добавьте следующие переменные в ваш `.env` файл:

## 📝 Переменные для .env файла

```bash
# ==================================================================
# HuggingFace Token
# ==================================================================
HF_TOKEN=your_huggingface_token_here

# ==================================================================
# MEDIUM Model Configuration (порт 8001)
# ==================================================================
VLLM_MODEL_MEDIUM=OpenGPT/gpt-oss-20b
VLLM_GPU_MEMORY_UTILIZATION_MEDIUM=0.85
VLLM_MAX_MODEL_LEN_MEDIUM=8192
VLLM_MAX_NUM_SEQS_MEDIUM=128

# ==================================================================
# SMALL Model Configuration (порт 8002)
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

# ==================================================================
# Common Settings
# ==================================================================
VLLM_TENSOR_PARALLEL_SIZE=1
VLLM_ENFORCE_EAGER=false
```

## 🚀 Способы использования

### Способ 1: Использовать основной .env файл (Рекомендуется)

Это самый простой способ. Docker Compose автоматически загрузит `.env`:

```bash
# 1. Добавьте переменные выше в ваш .env файл
vim .env

# 2. Получите MIG UUID
nvidia-smi -L
# или
bash scripts/list_mig_devices.sh

# 3. Обновите MIG_MEDIUM, MIG_SMALL, MIG_1G_24GB в .env

# 4. Запустите
docker-compose -f docker-compose.vllm-mig.yml up -d
# или
make up-vllm-mig
```

### Способ 2: Использовать отдельный .env файл

Если хотите использовать отдельный файл для vLLM конфигурации:

```bash
# 1. Создайте отдельный файл
cp ENV_SETUP_GUIDE.md .env.vllm-mig
vim .env.vllm-mig

# 2. Запустите с явным указанием файла
docker-compose --env-file .env.vllm-mig -f docker-compose.vllm-mig.yml up -d
```

### Способ 3: Экспортировать переменные в shell

Для временного использования:

```bash
# Экспортируйте переменные
export VLLM_MODEL_MEDIUM=OpenGPT/gpt-oss-20b
export VLLM_MODEL_SMALL=mistralai/Mistral-7B-Instruct-v0.3
export MIG_MEDIUM=MIG-GPU-xxxxx.../7/0
export MIG_SMALL=MIG-GPU-xxxxx.../14/0
export MIG_1G_24GB=MIG-GPU-xxxxx.../15/0

# Запустите
docker-compose -f docker-compose.vllm-mig.yml up -d
```

## 🔍 Получение MIG UUID

### Метод 1: nvidia-smi

```bash
nvidia-smi -L
```

Вывод:
```
GPU 0: NVIDIA RTX 6000 Ada Generation (UUID: GPU-12345678-1234-1234-1234-123456789abc)
  MIG 2g.48gb Device 0: (UUID: MIG-GPU-12345678-1234-1234-1234-123456789abc/7/0)
  MIG 1g.24gb Device 1: (UUID: MIG-GPU-12345678-1234-1234-1234-123456789abc/14/0)
  MIG 1g.24gb Device 2: (UUID: MIG-GPU-12345678-1234-1234-1234-123456789abc/15/0)
```

### Метод 2: Скрипт

```bash
bash scripts/list_mig_devices.sh
```

### Метод 3: nvidia-smi с детальной информацией

```bash
nvidia-smi mig -lgi  # List GPU Instances
nvidia-smi mig -lci  # List Compute Instances
```

## ⚙️ Обновление Makefile

Makefile уже настроен на использование стандартного `.env` файла. Команды:

```bash
# Запуск (использует .env автоматически)
make up-vllm-mig

# Для dual models с пользовательским .env файлом
make up-dual-models  # использует .env.vllm-dual-models если существует

# Логи
make logs-medium
make logs-small

# Тестирование
make test-dual-models
```

## 📋 Полный пример .env файла

```bash
# ==================================================================
# vLLM Dual Models Configuration
# ==================================================================

# HuggingFace Token (получите на https://huggingface.co/settings/tokens)
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ==================================================================
# MEDIUM Model (большая модель, 2g.48gb MIG, порт 8001)
# ==================================================================
VLLM_MODEL_MEDIUM=OpenGPT/gpt-oss-20b
VLLM_GPU_MEMORY_UTILIZATION_MEDIUM=0.85
VLLM_MAX_MODEL_LEN_MEDIUM=8192
VLLM_MAX_NUM_SEQS_MEDIUM=128

# ==================================================================
# SMALL Model (меньшая модель, 1g.24gb MIG, порт 8002)
# ==================================================================
VLLM_MODEL_SMALL=mistralai/Mistral-7B-Instruct-v0.3
VLLM_GPU_MEMORY_UTILIZATION_SMALL=0.90
VLLM_MAX_MODEL_LEN_SMALL=16384
VLLM_MAX_NUM_SEQS_SMALL=256

# ==================================================================
# MIG Devices (замените на ваши UUID)
# ==================================================================
MIG_MEDIUM=MIG-GPU-12345678-1234-1234-1234-123456789abc/7/0
MIG_SMALL=MIG-GPU-12345678-1234-1234-1234-123456789abc/14/0
MIG_1G_24GB=MIG-GPU-12345678-1234-1234-1234-123456789abc/15/0

# ==================================================================
# Common Settings
# ==================================================================
VLLM_TENSOR_PARALLEL_SIZE=1
VLLM_ENFORCE_EAGER=false

# Qdrant
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=docs

# Embeddings
EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Backend LLM (использует MEDIUM model по умолчанию)
LLM_MODE=vllm
LLM_VLLM_URL=http://vllm-medium:8001/v1
LLM_TIMEOUT=120
LLM_MAX_TOKENS=512
LLM_TEMPERATURE=0.3

# Document Processing
CHUNK_TOKENS=400
CHUNK_OVERLAP=50

# Search & RAG
CONTEXT_MAX_CHUNKS=6
TOP_K_DEFAULT=6

# Caching
CACHE_ENABLED=true
CACHE_TTL_SECONDS=600
```

## 🔄 Переключение между конфигурациями

### Для разных окружений

```bash
# Development
cp .env.dev .env
make up-vllm-mig

# Production
cp .env.prod .env
make up-vllm-mig

# Testing
cp .env.test .env
make up-vllm-mig
```

### Использование симлинка

```bash
# Создать симлинк на текущую конфигурацию
ln -sf .env.vllm-mig .env

# Переключиться на другую
rm .env
ln -sf .env.ollama .env
```

## 🎯 Проверка конфигурации

После настройки `.env` файла:

```bash
# 1. Проверьте переменные
cat .env | grep -E "VLLM_MODEL|MIG_"

# 2. Проверьте, что docker-compose видит переменные
docker-compose -f docker-compose.vllm-mig.yml config | grep VLLM_MODEL

# 3. Запустите
docker-compose -f docker-compose.vllm-mig.yml up -d

# 4. Проверьте health
curl http://localhost:8001/health
curl http://localhost:8002/health

# 5. Проверьте модели
curl http://localhost:8001/v1/models
curl http://localhost:8002/v1/models
```

## 📚 Примеры моделей

### Для MEDIUM model (2g.48gb, ~40-48 GB)

```bash
# 20B параметров, общего назначения
VLLM_MODEL_MEDIUM=OpenGPT/gpt-oss-20b

# 13B параметров, от Meta
VLLM_MODEL_MEDIUM=meta-llama/Llama-2-13b-chat-hf

# MoE модель, высокая производительность
VLLM_MODEL_MEDIUM=mistralai/Mixtral-8x7B-Instruct-v0.1

# 11B параметров, эффективная
VLLM_MODEL_MEDIUM=upstage/SOLAR-10.7B-Instruct-v1.0
```

### Для SMALL model (1g.24gb, ~14-20 GB)

```bash
# 7B параметров, хорошо для кода
VLLM_MODEL_SMALL=mistralai/Mistral-7B-Instruct-v0.3

# 7B параметров, от Meta
VLLM_MODEL_SMALL=meta-llama/Llama-2-7b-chat-hf

# 7B параметров, хорошо следует инструкциям
VLLM_MODEL_SMALL=teknium/OpenHermes-2.5-Mistral-7B

# 7B параметров, поддержка функций
VLLM_MODEL_SMALL=NousResearch/Hermes-2-Pro-Mistral-7B
```

## 🐛 Troubleshooting

### Проблема: Docker Compose не загружает .env

**Решение:**
```bash
# Убедитесь, что .env в корне проекта
ls -la .env

# Проверьте права доступа
chmod 644 .env

# Явно укажите файл
docker-compose --env-file .env -f docker-compose.vllm-mig.yml up -d
```

### Проблема: MIG устройства не найдены

**Решение:**
```bash
# Проверьте MIG
nvidia-smi -L

# Настройте MIG если нужно
sudo bash scripts/setup_mig.sh

# Проверьте device_ids доступность
docker run --rm --gpus device=${MIG_MEDIUM} nvidia/cuda:12.0-base nvidia-smi
```

### Проблема: Переменные не подставляются

**Решение:**
```bash
# Убедитесь в правильном формате (без пробелов вокруг =)
# Правильно:
VLLM_MODEL_MEDIUM=OpenGPT/gpt-oss-20b

# Неправильно:
VLLM_MODEL_MEDIUM = OpenGPT/gpt-oss-20b

# Проверьте что переменные экспортируются
docker-compose -f docker-compose.vllm-mig.yml config
```

## 💡 Советы

1. **Используйте основной .env файл** - Docker Compose автоматически его загружает
2. **Храните шаблон** - создайте `.env.template` для команды
3. **Не коммитьте .env** - убедитесь что он в `.gitignore`
4. **Используйте комментарии** - документируйте каждую переменную
5. **Группируйте переменные** - по сервисам или функциональности

## 📖 Дополнительные ресурсы

- [Docker Compose Environment Variables](https://docs.docker.com/compose/environment-variables/)
- [NVIDIA MIG User Guide](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/)
- [vLLM Environment Variables](https://docs.vllm.ai/en/latest/serving/env_vars.html)

