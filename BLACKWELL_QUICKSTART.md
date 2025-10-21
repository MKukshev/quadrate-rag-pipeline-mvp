# Blackwell Quick Start для RTX 6000 Blackwell 96GB

## 🚀 Основные преимущества Blackwell

- ✅ **2x производительность** vs Ada Lovelace
- ✅ **FP8 precision** - запуск Llama-70B на одной GPU!
- ✅ **До 400 tokens/sec** для Llama-8B  
- ✅ **128K контекст** без проблем
- ✅ **Улучшенные Tensor Cores** для transformers

## 📋 Что изменилось vs Ada

| Параметр | Ada (старая конфиг) | Blackwell (новая) |
|----------|---------------------|-------------------|
| CUDA | 12.1 | **12.4+** ✅ |
| vLLM | 0.4.2 | **0.6.2+** ✅ |
| GPU Memory | 0.90 | **0.95** ✅ |
| Max Context | 8K | **16K** ✅ |
| Max Seqs | 256 | **512** ✅ |
| FP8 Support | ❌ | **✅** |
| FlashInfer | ❌ | **✅** |

## 🚀 Быстрый старт (Llama-8B)

```bash
# 1. Обновить конфигурацию
cp .env.vllm .env
nano .env  # Добавить HUGGING_FACE_HUB_TOKEN

# 2. Запустить (автоматически использует Blackwell оптимизации)
make up-vllm

# 3. Проверить
curl http://localhost:8000/health
```

## 🎯 Запуск Llama-70B с FP8 (только на Blackwell!)

```bash
# 1. Использовать FP8 конфигурацию
cp .env.vllm-fp8 .env

# 2. Обновить токен
nano .env  # HUGGING_FACE_HUB_TOKEN=hf_xxxxx

# 3. Запустить 70B модель!
make up-vllm

# Модель: neuralmagic/Meta-Llama-3.1-70B-Instruct-FP8
# VRAM: ~70GB (влезает в 96GB!)
# Скорость: 200-300 tokens/sec
```

## 📊 Рекомендуемые модели

### Без FP8 (FP16/BF16)
```bash
# Llama-8B - максимальная скорость
VLLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
# → 300-400 tokens/sec, 16GB VRAM

# Mixtral-8x7B - большой контекст
VLLM_MODEL=mistralai/Mixtral-8x7B-Instruct-v0.1  
# → 200-280 tokens/sec, 48GB VRAM
```

### С FP8 (рекомендуется для Blackwell)
```bash
# Llama-70B FP8 - лучший баланс
VLLM_MODEL=neuralmagic/Meta-Llama-3.1-70B-Instruct-FP8
# → 200-300 tokens/sec, 70GB VRAM ✅

# Qwen-72B FP8 - длинный контекст
VLLM_MODEL=Qwen/Qwen2.5-72B-Instruct-FP8
# → 180-250 tokens/sec, 72GB VRAM ✅
```

## ⚙️ Включить все Blackwell оптимизации

```bash
# В .env
VLLM_GPU_MEMORY_UTILIZATION=0.95    # Выше чем Ada
VLLM_MAX_MODEL_LEN=16384             # Больше контекст
VLLM_MAX_NUM_SEQS=512                # Больше батчинг
VLLM_ENABLE_FP8=true                 # FP8 precision
VLLM_USE_FLASHINFER=true             # FlashInfer attention
VLLM_ENABLE_CHUNKED_PREFILL=true     # Chunked prefill
```

## 🔍 Проверка системы

```bash
# CUDA версия (должна быть 12.4+)
nvidia-smi

# Compute capability (должна быть 10.0 для Blackwell)
nvidia-smi --query-gpu=compute_cap --format=csv

# Драйвер (должен быть 550+)
nvidia-smi --query-gpu=driver_version --format=csv
```

## 📚 Полная документация

- [docs/BLACKWELL_OPTIMIZATIONS.md](docs/BLACKWELL_OPTIMIZATIONS.md) - Все оптимизации
- [docs/VLLM_DEPLOYMENT.md](docs/VLLM_DEPLOYMENT.md) - vLLM развертывание
- [MIG_QUICKSTART.md](MIG_QUICKSTART.md) - MIG для Blackwell

## 💡 Совет

**Для максимальной производительности:**
1. Используйте FP8 модели (`.env.vllm-fp8`)
2. Включите FlashInfer (`VLLM_USE_FLASHINFER=true`)
3. Увеличьте batch size (`VLLM_MAX_NUM_SEQS=512`)

Blackwell в 2x быстрее Ada Lovelace! 🚀

