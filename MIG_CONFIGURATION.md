# Конфигурация MIG для RTX 6000 Blackwell 96GB

## Ваша конфигурация

```
RTX 6000 96GB (MIG enabled)
├── 1g.24gb: 2 инстанса (GI 1, 5)
└── 2g.48gb: 1 инстанс (GI 2, 3, или 4)
```

---

## Шаг 1: Найдите UUID ваших MIG инстансов

```bash
nvidia-smi -L

# Должен показать что-то вроде:
# GPU 0: NVIDIA RTX PRO 6000 Blackwell
# MIG-GPU-abc12345-6789-0123-4567-abc123456789/1/0
# MIG-GPU-abc12345-6789-0123-4567-abc123456789/5/0
# MIG-GPU-abc12345-6789-0123-4567-abc123456789/X/0  ← Это ваш 2g.48gb
```

**Важно:** Нужно определить какой GI (GPU Instance) соответствует 2g.48gb.

```bash
# Показывает детальную информацию о MIG инстансах
nvidia-smi -q -d MIG | grep -A 5 "GPU Instance"

# Или через query
nvidia-smi --query-gpu=index,name,mig.mode.current,mig.mode.pending --format=csv
```

---

## Шаг 2: Создайте .env.vllm-mig файл

Создайте файл `.env.vllm-mig` с вашими UUID:

```bash
# Пример .env.vllm-mig

# vLLM использует 2g.48gb инстанс (для Llama-70B FP8)
MIG_2G_48GB=MIG-GPU-abc12345-6789-0123-4567-abc123456789/2/0

# Backend использует один из 1g.24gb инстансов (для embeddings)
MIG_1G_24GB=MIG-GPU-abc12345-6789-0123-4567-abc123456789/1/0

# Модель
VLLM_MODEL=neuralmagic/Meta-Llama-3.1-70B-Instruct-FP8

# HuggingFace токен
HUGGING_FACE_HUB_TOKEN=hf_xxxxx

# GPU параметры для 48GB инстанса
VLLM_GPU_MEMORY_UTILIZATION=0.95
VLLM_MAX_MODEL_LEN=16384
VLLM_TENSOR_PARALLEL_SIZE=1
```

---

## Шаг 3: Обновите docker-compose.vllm-mig.yml

В `docker-compose.vllm-mig.yml` уже есть поддержка MIG. Нужно только настроить:

**Для vLLM:**
```yaml
vllm:
  environment:
    - CUDA_VISIBLE_DEVICES=${MIG_2G_48GB}
    - NVIDIA_VISIBLE_DEVICES=${MIG_2G_48GB}
  
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ["${MIG_2G_48GB}"]
            capabilities: [gpu]
```

**Для backend:**
```yaml
backend:
  environment:
    - CUDA_VISIBLE_DEVICES=${MIG_1G_24GB}
    - NVIDIA_VISIBLE_DEVICES=${MIG_1G_24GB}
  
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ["${MIG_1G_24GB}"]
            capabilities: [gpu]
```

---

## Шаг 4: Запустите

```bash
# 1. Установите переменные окружения
export MIG_2G_48GB="MIG-GPU-xxx/2/0"  # Замените на ваш UUID
export MIG_1G_24GB="MIG-GPU-xxx/1/0"  # Замените на ваш UUID

# 2. Или используйте .env файл
cp .env.vllm-mig .env
nano .env  # Добавьте ваши UUID

# 3. Запустите
docker compose -f docker-compose.vllm-mig.yml up -d

# 4. Проверьте
docker compose -f docker-compose.vllm-mig.yml exec vllm nvidia-smi
docker compose -f docker-compose.vllm-mig.yml exec backend nvidia-smi
```

---

## Проверка

### Проверить какой MIG используется vLLM

```bash
docker compose -f docker-compose.vllm-mig.yml exec vllm nvidia-smi

# Должно показать только ваш 2g.48gb инстанс (48GB)
```

### Проверить какой MIG используется backend

```bash
docker compose -f docker-compose.vllm-mig.yml exec backend nvidia-smi

# Должно показать только ваш 1g.24gb инстанс (24GB)
```

### Проверить что backend использует GPU

```bash
docker compose -f docker-compose.vllm-mig.yml exec backend python3 -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
```

---

## Troubleshooting

### Ошибка: "device not found"

**Проблема:** UUID неправильный или инстанс не существует

**Решение:**
```bash
# Проверьте правильность UUID
nvidia-smi -L | grep "MIG-GPU"

# Убедитесь что формат правильный
echo $MIG_2G_48GB
# Должно быть: MIG-GPU-xxx/X/0
```

### Ошибка: "insufficient resources"

**Проблема:** Недостаточно памяти на MIG инстансе

**Решение:**
- Для vLLM: Уменьшите `VLLM_GPU_MEMORY_UTILIZATION` (например, 0.85)
- Для Backend: 24GB достаточно для embeddings, проблем быть не должно

### Определить GI для 2g.48gb

```bash
# Список всех MIG инстансов
nvidia-smi -q -d MIG

# Найдите инстанс с 48GB
# GI (GPU Instance) обычно:
# - 2g.48gb → GI 2, 3, или 4
# - 1g.24gb → GI 1, 5, 6
```

---

## Рекомендуемое распределение

Для вашей конфигурации:
```
2g.48gb (один инстанс) → vLLM для Llama-70B FP8
1g.24gb (первый)       → Backend для embeddings/reranking  
1g.24gb (второй)       → Reserved / Future
```

Это оптимальное распределение!

---

## Пример полной команды запуска

```bash
# 1. Найдите UUID
nvidia-smi -L

# 2. Установите переменные (замените xxx на реальные UUID)
export MIG_2G_48GB="MIG-GPU-abc12345-6789-0123-4567-abc123456789/2/0"
export MIG_1G_24GB="MIG-GPU-abc12345-6789-0123-4567-abc123456789/1/0"

# 3. Запустите
docker compose -f docker-compose.vllm-mig.yml up -d

# 4. Проверьте логи
docker compose -f docker-compose.vllm-mig.yml logs -f
```

Готово! Ваш vLLM теперь работает на 2g.48gb инстансе, а backend на 1g.24gb.
