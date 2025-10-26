# Конфигурация для GPT-OSS-20B

## Требования к GPU

**Модель**: `OpenGPT/gpt-oss-20b` (20B параметров)

### Варианты загрузки:

1. **FP16 (Full Precision)**: ~40GB GPU memory
2. **FP8 (черновая поддержка в vLLM 0.6.2)**: ~20GB GPU memory  
3. **INT8 (квантованная)**: ~24GB GPU memory

## Конфигурация для MIG инстанса (2g.48gb = 48GB)

### Вариант 1: INT8 квантование (рекомендуется)

```bash
# docker-compose.vllm-mig.yml
environment:
  # Модель
  - VLLM_MODEL=OpenGPT/gpt-oss-20b
  
  # GPU параметры (INT8)
  - VLLM_GPU_MEMORY_UTILIZATION=0.85  # 48GB * 0.85 = 40.8GB доступно
  - VLLM_MAX_MODEL_LEN=8192
  - VLLM_TENSOR_PARALLEL_SIZE=1
  - VLLM_MAX_NUM_SEQS=128  # Уменьшено для экономии памяти
  
  # Квантование INT8
  - VLLM_QUANTIZATION=awq  # или gptq
  
  # Дополнительно для 20B модели
  - VLLM_ENABLE_CHUNKED_PREFILL=true
  - VLLM_ENABLE_PREFILL_TO_DECODE_DETACH=true
```

### Вариант 2: FP16 без квантования (если модель поддерживает)

```bash
environment:
  - VLLM_MODEL=OpenGPT/gpt-oss-20b
  - VLLM_GPU_MEMORY_UTILIZATION=0.90
  - VLLM_MAX_MODEL_LEN=4096  # Уменьшено для 20B
  - VLLM_MAX_NUM_SEQS=64
```

## Переменные окружения

```bash
# В .env файле
VLLM_MODEL=OpenGPT/gpt-oss-20b
VLLM_GPU_MEMORY_UTILIZATION=0.85
VLLM_MAX_MODEL_LEN=8192
VLLM_TENSOR_PARALLEL_SIZE=1
VLLM_QUANTIZATION=awq  # активировать квантование

# HuggingFace токен (обязателен для gated моделей)
HUGGING_FACE_HUB_TOKEN=hf_xxxxx
```

## Запуск

```bash
# 1. Установите переменные
export MIG_2G_48GB="MIG-GPU-xxx/2/0"
export MIG_1G_24GB="MIG-GPU-xxx/1/0"

# 2. Соберите и запустите
docker compose -f docker-compose.vllm-mig.yml up -d --build

# 3. Мониторинг загрузки
docker compose -f docker-compose.vllm-mig.yml logs -f vllm

# 4. Проверка памяти
docker compose -f docker-compose.vllm-mig.yml exec vllm nvidia-smi
```

## Ожидаемое время загрузки

- **Загрузка модели**: 2-5 минут (зависит от сети)
- **Инициализация vLLM**: 1-3 минуты
- **Первое поколение**: может быть медленнее

## Изменения в backend

Backend автоматически подхватит новую модель через переменную:
```bash
LLM_MODEL=${VLLM_MODEL:-OpenGPT/gpt-oss-20b}
```

## Проверка работоспособности

```bash
# Health check
curl http://localhost:8000/health

# Тест LLM
curl -X POST http://localhost:8001/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "OpenGPT/gpt-oss-20b",
    "prompt": "Hello, world!",
    "max_tokens": 50
  }'
```

## Сравнение с текущей моделью

| Параметр | Llama-3.1-8B (текущая) | GPT-OSS-20B |
|----------|------------------------|-------------|
| Параметров | 8B | 20B |
| GPU memory (FP16) | ~16GB | ~40GB |
| GPU memory (FP8/INT8) | ~8GB | ~20GB |
| Контекстное окно | 16384 | 8192 (рекомендуется) |
| Скорость инференса | ~50 tokens/sec | ~30-40 tokens/sec |
| Качество | Хорошее | Отличное |

