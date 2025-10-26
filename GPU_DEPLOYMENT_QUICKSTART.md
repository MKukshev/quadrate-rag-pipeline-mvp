# 🚀 Быстрый старт: Развертывание на GPU сервере

## ⚡ В 3 шага

### 1️⃣ Подготовка сервера

```bash
# Проверить GPU
nvidia-smi

# Установить Docker + NVIDIA Container Toolkit
curl -fsSL https://get.docker.com | sh
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Проверить GPU в Docker
docker run --rm --gpus all nvidia/cuda:12.6.1-base-ubuntu22.04 nvidia-smi
```

### 2️⃣ Клонировать и настроить

```bash
# Клонировать репозиторий
git clone https://github.com/your-org/ai-assistant-mvp.git
cd ai-assistant-mvp

# Создать .env
cp .env.vllm .env
nano .env  # Добавить HUGGING_FACE_HUB_TOKEN=hf_xxxxx
```

### 3️⃣ Запустить

```bash
# Запустить весь стек
make up-vllm

# Дождаться готовности
make wait

# Проверить
curl http://localhost:8000/health
```

✅ **Готово!** API доступен на `http://localhost:8000`

---

## 🎯 Выбор конфигурации

### RTX 6000 Blackwell 96GB (Рекомендуется)

```bash
# Вариант A: Llama-8B (быстро)
cp .env.vllm .env
make up-vllm
# → 300-400 tokens/sec

# Вариант B: Llama-70B FP8 (качество) 
cp .env.vllm-fp8 .env
nano .env  # Добавить HF токен
make up-vllm
# → 200-300 tokens/sec, влезает в 96GB!
```

### Другие GPU (RTX 4090, A100, H100)

```bash
# 1. Создать .env
cp .env.vllm .env

# 2. Настроить для вашего GPU
nano .env

# Пример для RTX 4090 (24GB):
VLLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
VLLM_GPU_MEMORY_UTILIZATION=0.9
VLLM_MAX_MODEL_LEN=8192

# 3. Запустить
make up-vllm
```

---

## 📊 Проверка работы

### 1. Health Check

```bash
curl http://localhost:8000/health | jq

# Должен вернуть:
# {
#   "status": "ok",
#   "qdrant": "connected",
#   "llm": "vllm",
#   "model": "Meta-Llama-3.1-8B-Instruct"
# }
```

### 2. Индексация документов

```bash
# Индексировать примеры документов
make ingest SPACE=production

# Или через API
curl -X POST http://localhost:8000/ingest \
  -F "file=@document.pdf" \
  -F "space_id=production"
```

### 3. Тестовый запрос

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "q": "Какие дедлайны у проекта?",
    "space_id": "production",
    "top_k": 6
  }' | jq
```

---

## 🔍 Мониторинг

### Проверка GPU

```bash
# В реальном времени
watch -n 1 nvidia-smi

# Использование памяти, загрузка, температура
```

### Проверка метрик

```bash
# Токен/сек, задержка, cache hit rate
curl http://localhost:8000/metrics | jq

# Логи vLLM
make logs-vllm
```

---

## 🎛️ Полезные команды

```bash
# Запуск
make up-vllm

# Остановка
make down-vllm

# Логи
make logs-vllm

# Перезапуск
docker compose -f docker-compose.vllm.yml restart

# Обновить модель
nano .env  # Изменить VLLM_MODEL
make down-vllm && make up-vllm
```

---

## ⚙️ Оптимизация производительности

### Для Blackwell

```bash
# В .env добавить оптимизации:
VLLM_ENABLE_FP8=true
VLLM_USE_FLASHINFER=true
VLLM_ENABLE_CHUNKED_PREFILL=true
VLLM_MAX_NUM_SEQS=512
VLLM_GPU_MEMORY_UTILIZATION=0.95
```

### Для других GPU

```bash
# В backend/.env оптимизировать контекст:
CONTEXT_MAX_CHUNKS=8
CONTEXT_SNIPPET_MAX_CHARS=800
```

---

## 🚨 Troubleshooting

### Проблема: "CUDA out of memory"

```bash
# Уменьшить memory utilization
VLLM_GPU_MEMORY_UTILIZATION=0.85
```

### Проблема: "Docker GPU not found"

```bash
sudo systemctl restart docker
docker run --rm --gpus all nvidia/cuda:12.6.1-base nvidia-smi
```

### Проблема: "Медленная генерация"

```bash
# Включить оптимизации
VLLM_USE_FLASHINFER=true
VLLM_ENABLE_CHUNKED_PREFILL=true

# Уменьшить контекст
CONTEXT_MAX_CHUNKS=4
```

---

## 📚 Документация

- [Полное руководство по развертыванию](docs/GPU_DEPLOYMENT_GUIDE.md)
- [Blackwell оптимизации](docs/BLACKWELL_OPTIMIZATIONS.md)
- [vLLM развертывание](docs/VLLM_DEPLOYMENT.md)
- [Рекомендации по инфраструктуре](deploy_recommendations.md)

---

## 🎯 Production Checklist

Перед запуском в production:

- [ ] Firewall настроен
- [ ] SSL/TLS через nginx
- [ ] Мониторинг настроен
- [ ] Логирование настроено
- [ ] Backup настроен
- [ ] Тесты проведены
