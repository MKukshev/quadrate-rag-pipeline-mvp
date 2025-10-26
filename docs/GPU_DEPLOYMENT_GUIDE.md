# Полное руководство по развертыванию на GPU сервере

## 📋 Содержание

1. [Обзор развертывания](#обзор)
2. [Требования к серверу](#требования)
3. [Подготовка сервера](#подготовка)
4. [Развертывание на RTX 6000 Blackwell](#blackwell-deployment)
5. [Развертывание на других GPU](#другие-gpu)
6. [Миграция с Ollama на vLLM](#миграция)
7. [Мониторинг и оптимизация](#мониторинг)
8. [Troubleshooting](#troubleshooting)

---

## 🎯 Обзор {#обзор}

Этот RAG-пайплайн может работать в трех режимах:

| Режим | GPU | Скорость | Модели | Конфиг файл |
|-------|-----|----------|---------|-------------|
| **Ollama** | Опционально | 40-60 tokens/sec | 8B на CPU, до 70B на GPU | `docker-compose.yml` |
| **vLLM** | Обязательно | 150-400 tokens/sec | 8B-70B+ | `docker-compose.vllm.yml` |
| **vLLM+MIG** | Обязательно | Параллельно | 8B x 6 инстансов | `docker-compose.vllm-mig.yml` |

### Рекомендуемые конфигурации:

**Для RTX 6000 Blackwell 96GB:**
- ⭐ **Рекомендуется:** vLLM с FP8 моделями
- Модели: Llama-70B FP8, Qwen-72B FP8
- Throughput: 200-300 tokens/sec, 15-30 req/s

**Для других GPU (RTX 4090, A100, H100):**
- vLLM с FP16/BF16 моделями
- Модели: Llama-8B, Mistral-7B, Mixtral-8x7B
- Throughput: 100-250 tokens/sec

---

## 🖥️ Требования к серверу {#требования}

### Минимальные требования (Ollama без GPU):
- CPU: 8 cores
- RAM: 16 GB
- Disk: 50 GB SSD
- GPU: Не требуется (медленно)

### Рекомендуемые требования (vLLM с GPU):
- **GPU:** NVIDIA GPU с 16GB+ VRAM (RTX 4090, A100, H100)
- **CPU:** 8-16 cores
- **RAM:** 32-64 GB
- **Disk:** 200 GB NVMe SSD
- **CUDA:** 12.4+ для Blackwell, 11.8+ для других
- **Docker:** 24.0+ с GPU support

### Оптимальные требования (vLLM на RTX 6000 Blackwell):
- **GPU:** RTX 6000 Blackwell 96GB
- **CPU:** 16+ cores
- **RAM:** 64-128 GB
- **Disk:** 500 GB+ NVMe SSD
- **CUDA:** 12.6.1+
- **vLLM:** 0.6.2+

---

## 🛠️ Подготовка сервера {#подготовка}

### 1. Установка NVIDIA драйвера и CUDA

```bash
# Проверить версию драйвера
nvidia-smi

# Установить CUDA 12.6.1 для Blackwell
wget https://developer.download.nvidia.com/compute/cuda/12.6.1/local_installers/cuda_12.6.1_550.54.15_linux.run
sudo sh cuda_12.6.1_550.54.15_linux.run

# Добавить в PATH
echo 'export PATH=/usr/local/cuda-12.6/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.6/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

### 2. Установка Docker и NVIDIA Container Toolkit

```bash
# Установить Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Установить NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Проверить GPU доступен в Docker
docker run --rm --gpus all nvidia/cuda:12.6.1-base-ubuntu22.04 nvidia-smi
```

### 3. Клонирование репозитория

```bash
# Клонировать проект
git clone https://github.com/your-org/ai-assistant-mvp.git
cd ai-assistant-mvp

# Создать .env файл
cp .env.example .env

# Добавить HuggingFace токен
nano .env
# HUGGING_FACE_HUB_TOKEN=hf_xxxxxxxxxxxxxxxx
```

---

## 🚀 Развертывание на RTX 6000 Blackwell {#blackwell-deployment}

### Вариант 1: Базовое развертывание с vLLM

```bash
# 1. Использовать конфигурацию vLLM
cp .env.vllm .env

# 2. Запустить сервисы
make up-vllm

# 3. Дождаться готовности (2-5 минут для загрузки модели)
make wait

# 4. Проверить health
curl http://localhost:8000/health
```

**Что запускается:**
- Qdrant (vector database) на порту 6333
- vLLM сервер на порту 8001
- Backend API на порту 8000

**Модель по умолчанию:** `Meta-Llama-3.1-8B-Instruct`
**Производительность:** 300-400 tokens/sec

### Вариант 2: Развертывание с FP8 моделью (Llama-70B!)

```bash
# 1. Использовать FP8 конфигурацию
cp .env.vllm-fp8 .env

# 2. Добавить HF токен
nano .env
# HUGGING_FACE_HUB_TOKEN=hf_xxxxx

# 3. Запустить
make up-vllm

# 4. Проверить
curl http://localhost:8000/health
```

**Модель:** `neuralmagic/Meta-Llama-3.1-70B-Instruct-FP8`
**VRAM:** ~70GB (влезает в 96GB!)
**Производительность:** 200-300 tokens/sec

### Вариант 3: Развертывание с MIG (Multi-Instance GPU)

MIG позволяет разбить RTX 6000 96GB на 6 независимых инстансов:

```bash
# 1. Настроить MIG
make setup-mig

# 2. Проверить MIG инстансы
make list-mig

# 3. Запустить с MIG
make up-vllm-mig

# Каждый инстанс = отдельная модель!
```

См. [MIG_QUICKSTART.md](../MIG_QUICKSTART.md) для подробностей.

---

## 🖥️ Развертывание на других GPU {#другие-gpu}

### RTX 4090 (24GB)

```bash
# 1. Создать .env
cp .env.vllm .env

# 2. Настроить модель под 24GB
cat >> .env << EOF
VLLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
VLLM_GPU_MEMORY_UTILIZATION=0.9
VLLM_MAX_MODEL_LEN=8192
EOF

# 3. Запустить
make up-vllm
```

**Поддерживаемые модели:**
- Llama-8B ✅
- Mistral-7B ✅
- Mixtral-8x7B (с quantization)

### A100 40GB / H100 80GB

```bash
# 1. Создать .env
cp .env.vllm .env

# 2. Настроить для A100/H100
cat >> .env << EOF
VLLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
VLLM_GPU_MEMORY_UTILIZATION=0.95
VLLM_MAX_MODEL_LEN=16384
VLLM_TENSOR_PARALLEL_SIZE=1
EOF

# 3. Запустить
make up-vllm
```

**Для H100 можно запустить:**
- Llama-70B ✅
- Mixtral-8x7B ✅
- Qwen-72B (с FP8)

---

## 🔄 Миграция с Ollama на vLLM {#миграция}

### Шаг 1: Установить vLLM на сервер

```bash
# Клонировать проект
git clone https://github.com/your-org/ai-assistant-mvp.git
cd ai-assistant-mvp

# Использовать vLLM конфигурацию
cp .env.vllm .env
nano .env  # Добавить HF токен
```

### Шаг 2: Запустить vLLM вместо Ollama

```bash
# Остановить текущий стек (Ollama)
make down

# Запустить vLLM стек
make up-vllm

# Проверить
curl http://localhost:8000/health
```

### Шаг 3: Индексация данных

```bash
# Индексировать документы
make ingest SPACE=production

# Или через API
curl -X POST http://localhost:8000/ingest \
  -F "file=@document.pdf" \
  -F "space_id=production"
```

### Шаг 4: Тестирование

```bash
# Простой запрос
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "q": "Какие дедлайны у проекта?",
    "space_id": "production",
    "top_k": 6
  }'
```

---

## 📊 Мониторинг и оптимизация {#мониторинг}

### Мониторинг GPU

```bash
# Смотреть использование GPU
watch -n 1 nvidia-smi

# Проверить vLLM логи
make logs-vllm
```

### Мониторинг производительности

```bash
# Health check
curl http://localhost:8000/health | jq

# Метрики
curl http://localhost:8000/metrics | jq

# Популярные поля:
# - "tokens_per_second" - скорость генерации
# - "cache_hit_rate" - эффективность кэша
# - "avg_latency_ms" - средняя задержка
```

### Оптимизация производительности

#### 1. Увеличить GPU memory utilization

```bash
# В docker-compose.vllm.yml или .env
VLLM_GPU_MEMORY_UTILIZATION=0.95  # было 0.9
```

#### 2. Увеличить batch size

```bash
VLLM_MAX_NUM_SEQS=512  # было 256
```

#### 3. Включить оптимизации Blackwell

```bash
VLLM_ENABLE_FP8=true
VLLM_USE_FLASHINFER=true
VLLM_ENABLE_CHUNKED_PREFILL=true
```

#### 4. Оптимизировать контекст

```bash
# В backend/.env
CONTEXT_MAX_CHUNKS=8          # было 6
CONTEXT_SNIPPET_MAX_CHARS=800  # было 600
```

### Настройка Qdrant

```bash
# Оптимизировать HNSW для скорости
QDRANT_HNSW_M=32              # увеличить
QDRANT_HNSW_EF_CONSTRUCT=150
QDRANT_HNSW_EF_SEARCH=128
```

---

## 🔧 Troubleshooting {#troubleshooting}

### Проблема: "CUDA out of memory"

**Решение:**
```bash
# Уменьшить memory utilization
VLLM_GPU_MEMORY_UTILIZATION=0.85

# Или использовать меньшую модель
VLLM_MODEL=mistralai/Mistral-7B-Instruct-v0.2
```

### Проблема: "Docker GPU not found"

**Решение:**
```bash
# Проверить NVIDIA Container Toolkit
docker info | grep -i nvidia

# Перезапустить Docker
sudo systemctl restart docker

# Проверить GPU в контейнере
docker run --rm --gpus all nvidia/cuda:12.6.1-base nvidia-smi
```

### Проблема: "vLLM не запускается"

**Решение:**
```bash
# Проверить логи
make logs-vllm

# Общие причины:
# 1. CUDA версия не совместима
nvidia-smi  # должна быть 550+

# 2. Модель не скачалась
docker compose exec vllm ls /root/.cache/huggingface

# 3. Недостаточно VRAM
nvidia-smi  # проверить доступную память
```

### Проблема: "Медленная скорость генерации"

**Проверка:**
```bash
# 1. Проверить токен/сек
curl http://localhost:8000/metrics | jq .tokens_per_second

# 2. Проверить загрузку GPU
nvidia-smi

# 3. Проверить логи vLLM
make logs-vllm | grep "tokens/s"
```

**Решение:**
```bash
# 1. Включить оптимизации
VLLM_USE_FLASHINFER=true
VLLM_ENABLE_CHUNKED_PREFILL=true

# 2. Уменьшить контекст
CONTEXT_MAX_CHUNKS=4

# 3. Использовать quantization
VLLM_MODEL=neuralmagic/Meta-Llama-3.1-8B-Instruct-AWQ
```

### Проблема: "Backend не подключается к vLLM"

**Решение:**
```bash
# 1. Проверить vLLM health
curl http://localhost:8001/health

# 2. Проверить переменные окружения
docker compose exec backend env | grep VLLM

# 3. Перезапустить backend
docker compose restart backend
```

---

## 📚 Полезные команды

### Управление сервисами

```bash
# Запустить vLLM стек
make up-vllm

# Остановить
make down-vllm

# Логи
make logs-vllm

# Перезапустить
docker compose -f docker-compose.vllm.yml restart
```

### Работа с данными

```bash
# Индексировать документы
make ingest SPACE=production

# Протестировать запрос
make ask SPACE=production

# Проверить health
make health
```

### Отладка

```bash
# Логи backend
docker compose logs -f backend

# Логи vLLM
docker compose logs -f vLLM

# Логи Qdrant
docker compose logs -f qdrant

# Использование ресурсов
docker stats
```

### Обновление модели

```bash
# 1. Остановить vLLM
make down-vllm

# 2. Изменить модель в .env
VLLM_MODEL=meta-llama/Meta-Llama-3.1-70B-Instruct

# 3. Удалить старый кэш (опционально)
docker volume rm ai-assistant-mvp_vllm_cache

# 4. Запустить заново
make up-vllm
```

---

## 🎯 Production Checklist

Перед запуском в production:

- [ ] Настроен firewall (только нужные порты)
- [ ] SSL/TLS настроен (через nginx)
- [ ] Настроен мониторинг (Prometheus + Grafana)
- [ ] Настроены логи (ELK stack)
- [ ] Настроен backup данных (Qdrant volumes)
- [ ] Настроено логирование (log rotation)
- [ ] Настроена алертинг (Slack/PagerDuty)
- [ ] Протестирована нагрузка (benchmark)
- [ ] Настроены резервные копии (cron)
- [ ] Документированы процедуры восстановления

---

## 📖 Дополнительная документация

- [BLACKWELL_QUICKSTART.md](../BLACKWELL_QUICKSTART.md) - Быстрый старт для Blackwell
- [VLLM_QUICKSTART.md](../VLLM_QUICKSTART.md) - vLLM развертывание
- [MIG_QUICKSTART.md](../MIG_QUICKSTART.md) - MIG для RTX 6000
- [docs/BLACKWELL_OPTIMIZATIONS.md](BLACKWELL_OPTIMIZATIONS.md) - Оптимизации
- [docs/VLLM_DEPLOYMENT.md](VLLM_DEPLOYMENT.md) - Детали vLLM
- [deploy_recommendations.md](../deploy_recommendations.md) - Рекомендации по инфраструктуре
