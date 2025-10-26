# Развертывание с MIG (Multi-Instance GPU)

## Получение UUID MIG инстансов

```bash
# Список всех MIG инстансов
nvidia-smi -L

# Пример вывода:
# MIG-GPU-12345678-1234-1234-1234-123456789abc/1/0 (UUID: 12345678-1234-1234-1234-123456789abc)
# MIG-GPU-12345678-1234-1234-1234-123456789abc/5/0 (UUID: abcdef12-5678-9012-3456-abcdef123456)
```

---

## Конфигурация для 2g.48gb

### Шаг 1: Найдите UUID вашего 2g.48gb инстанса

```bash
# Список всех GPU и MIG устройств
nvidia-smi -L

# Должен показать что-то вроде:
# GPU 0: NVIDIA RTX PRO 6000 Blackwell
# MIG-GPU-<UUID>/1/0
# MIG-GPU-<UUID>/5/0  ← Эти два "1g.24gb"
# MIG-GPU-<UUID>/X/0  ← Этот "2g.48gb" (обычно GI 2-4)

# Получить детальную информацию
nvidia-smi -q -d MIG | grep -A 5 "GPU Instance"
```

### Шаг 2: Определите GI (GPU Instance) для 2g.48gb

```bash
# Показывает все MIG инстансы с размерами
nvidia-smi -q -d MIG | grep -B 10 "48GB"

# Или через query
nvidia-smi --query-gpu=index,name,mig.mode.current,mig.mode.pending --format=csv
```

**Обычно:**
- `1g.24gb` → GI 1, 5, 6 (меньшие)
- `2g.48gb` → GI 2, 3, 4 (больший)

---

## Docker Compose конфигурация

### Вариант 1: Использовать UUID напрямую

```yaml
# docker-compose.yml
services:
  vllm:
    environment:
      - CUDA_VISIBLE_DEVICES=MIG-GPU-12345678-1234-1234-1234-123456789abc/2/0
      - NVIDIA_VISIBLE_DEVICES=all
    
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["MIG-GPU-12345678-1234-1234-1234-123456789abc/2/0"]
              capabilities: [gpu]
```

### Вариант 2: Использовать через .env файл

**Создайте `.env.vllm-mig`:**

```bash
# .env.vllm-mig
MIG_DEVICE_UUID=MIG-GPU-12345678-1234-1234-1234-123456789abc/2/0
VLLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
VLLM_GPU_MEMORY_UTILIZATION=0.95
```

**docker-compose.vllm-mig.yml:**

```yaml
services:
  vllm:
    environment:
      - CUDA_VISIBLE_DEVICES=${MIG_DEVICE_UUID}
      - NVIDIA_VISIBLE_DEVICES=${MIG_DEVICE_UUID}
    
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["${MIG_DEVICE_UUID}"]
              capabilities: [gpu]
```

---

## Автоматический скрипт

```bash
#!/bin/bash
# scripts/get_mig_devices.sh

echo "=== MIG Devices ==="
nvidia-smi -L

echo ""
echo "=== GPU Instance Info ==="
nvidia-smi -q -d MIG | grep -A 5 "GPU Instance"

echo ""
echo "=== Extract UUIDs ==="
nvidia-smi -L | grep "MIG-GPU" | grep -o "MIG-GPU-[0-9a-f-]*/[0-9]/[0-9]" | sort -V
```

### Запуск с конкретным MIG

```bash
# 1. Найдите UUID вашего 2g.48gb инстанса
./scripts/get_mig_devices.sh

# 2. Экспортируйте UUID
export MIG_2G_48GB="MIG-GPU-xxx/2/0"  # Замените на ваш UUID

# 3. Запустите
docker compose -f docker-compose.vllm.yml up -d
```

---

## Пример: Конфигурация для вашего сервера

### Структура MIG

```
RTX 6000 96GB
├── 1g.24gb (2 инстанса) → GI 1, 5
│   ├── GI-1, CI-0 (24GB) - Backend
│   └── GI-5, CI-0 (24GB) - Reserve
└── 2g.48gb (1 инстанс) → GI 2
    └── GI-2, CI-0 (48GB) - vLLM для Llama-70B
```

### docker-compose.vllm-mig.yml для вашего сервера

```yaml
version: "3.9"

services:
  vllm:
    build:
      context: .
      dockerfile: backend/Dockerfile.vllm
    ports: ["8001:8001"]
    environment:
      # Модель
      - VLLM_MODEL=${VLLM_MODEL:-meta-llama/Meta-Llama-3.1-8B-Instruct}
      
      # GPU параметры (рассчитано для 48GB)
      - VLLM_GPU_MEMORY_UTILIZATION=${VLLM_GPU_MEMORY_UTILIZATION:-0.95}
      - VLLM_MAX_MODEL_LEN=${VLLM_MAX_MODEL_LEN:-16384}
      
      # HuggingFace токен
      - HUGGING_FACE_HUB_TOKEN=${HUGGING_FACE_HUB_TOKEN:-}
      
      # MIG: Используем 2g.48gb инстанс
      - CUDA_VISIBLE_DEVICES=${MIG_2G_48GB}
      - NVIDIA_VISIBLE_DEVICES=${MIG_2G_48GB}
    
    volumes:
      - vllm_cache:/root/.cache/huggingface
    
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["${MIG_2G_48GB}"]  # ← UUID вашего 2g.48gb
              capabilities: [gpu]
    
    restart: unless-stopped
    shm_size: '8gb'

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile.vllm
    command: ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
    ports: ["8000:8000"]
    environment:
      - LLM_MODE=vllm
      - LLM_VLLM_URL=http://vllm:8001/v1
      
      # MIG: Используем один из 1g.24gb инстансов
      - CUDA_VISIBLE_DEVICES=${MIG_1G_24GB}
      - NVIDIA_VISIBLE_DEVICES=${MIG_1G_24GB}
    
    volumes:
      - backend_data:/data
      - ./backend/models:/app/backend/models
      - ./backend:/app/backend:ro
      - ./docs:/app/docs:ro
      - ./config:/app/config:ro
      - ./cli:/app/cli:ro
    
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ["${MIG_1G_24GB}"]  # ← UUID одного из 1g.24gb
              capabilities: [gpu]
    
    restart: unless-stopped

volumes:
  vllm_cache:
  backend_data:
```

### .env.vllm-mig файл

```bash
# .env.vllm-mig

# Модель для vLLM
VLLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct

# HuggingFace токен
HUGGING_FACE_HUB_TOKEN=hf_xxxxx

# MIG Device UUIDs (найдите через nvidia-smi -L)
MIG_2G_48GB=MIG-GPU-abc123.../2/0   # Для vLLM (Llama-70B)
MIG_1G_24GB=MIG-GPU-abc123.../5/0   # Для Backend

# GPU параметры для 48GB
VLLM_GPU_MEMORY_UTILIZATION=0.95
VLLM_MAX_MODEL_LEN=16384
```

---

## Запуск

```bash
# 1. Найти UUID инстансов
nvidia-smi -L

# 2. Создать .env.vllm-mig с вашими UUID
nano .env.vllm-mig

# 3. Запустить
make up-vllm-mig

# Или напрямую
docker compose -f docker-compose.vllm-mig.yml --env-file .env.vllm-mig up -d
```

---

## Проверка

```bash
# Проверить какой MIG используется vLLM
docker compose -f docker-compose.vllm-mig.yml exec vllm nvidia-smi

# Проверить какой MIG используется backend
docker compose -f docker-compose.vllm-mig.yml exec backend nvidia-smi
```

---

## Troubleshooting

### Ошибка: "device not found"

```bash
# Убедитесь что UUID правильный
nvidia-smi -L | grep "2g.48gb"

# Проверьте формат
echo $MIG_2G_48GB
# Должно быть: MIG-GPU-xxx/X/0
```

### Ошибка: "insufficient resources"

```bash
# Проверьте что 2g.48gb инстанс действительно создан
nvidia-smi -q -d MIG | grep -A 10 "Compute Instance"

# Убедитесь что инстанс не занят другим контейнером
nvidia-smi
```

---

## Рекомендуемое распределение

Для вашего сервера с конфигурацией:
- `1g.24gb`: 2 инстанса
- `2g.48gb`: 1 инстанс

**Рекомендация:**

```
2g.48gb (GI-2) → vLLM для Llama-70B (требует 70GB, но поместится с quantization)
1g.24gb (GI-1) → Backend для embeddings (всего 384 dims, ~10GB)
1g.24gb (GI-5) → Reserved / Future use
```

Это оптимальное распределение для production!
