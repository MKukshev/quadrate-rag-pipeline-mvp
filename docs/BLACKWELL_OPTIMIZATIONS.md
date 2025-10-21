# Оптимизации для NVIDIA RTX 6000 Blackwell 96GB

## 🚀 Архитектура Blackwell

RTX 6000 Blackwell - новейшая архитектура NVIDIA с существенными улучшениями:

### Ключевые преимущества для vLLM

✅ **FP4 precision** - новый формат квантизации с минимальной потерей качества  
✅ **Двойная пропускная способность FP8** - 2x быстрее чем Ada Lovelace  
✅ **Улучшенные Tensor Cores (6-го поколения)** - специализированные для transformer моделей  
✅ **512GB/s memory bandwidth** - быстрая загрузка весов  
✅ **Second-generation Transformer Engine** - автоматическая оптимизация точности  
✅ **NVLink 5** - до 1.8TB/s между GPU (для multi-GPU)  
✅ **96GB HBM3e** - большой контекст и батчинг

## 📊 Требования

### Минимальные версии

| Компонент | Минимум | Рекомендуется | Почему |
|-----------|---------|---------------|--------|
| **CUDA** | 12.4 | 12.6+ | Blackwell compute capability 10.0 |
| **NVIDIA Driver** | 550+ | 560+ | Поддержка Blackwell |
| **vLLM** | 0.6.0 | 0.6.2+ | Оптимизации для Blackwell |
| **PyTorch** | 2.4 | 2.5+ | FP8/FP4 precision |
| **cuBLAS** | 12.4 | 12.6+ | Оптимизированный GEMM |

### Проверка системы

```bash
# Проверить CUDA версию
nvcc --version

# Проверить драйвер
nvidia-smi

# Должно быть: Driver Version: 550+ и CUDA Version: 12.4+

# Проверить compute capability
nvidia-smi --query-gpu=compute_cap --format=csv
# Должно быть: 10.0 для Blackwell
```

## 🔧 Оптимизированная конфигурация

### 1. Dockerfile обновлен для Blackwell

```dockerfile
# CUDA 12.4+ обязательно для Blackwell
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

# vLLM 0.6.2+ с оптимизациями Blackwell
RUN pip3 install vllm==0.6.2
```

### 2. Docker Compose параметры

```yaml
# docker-compose.vllm.yml
vllm:
  environment:
    # Blackwell-specific optimizations
    - VLLM_ENABLE_FP8=true              # FP8 precision (Blackwell оптимизация)
    - VLLM_USE_FLASHINFER=true          # FlashInfer для улучшенного attention
    - VLLM_GPU_MEMORY_UTILIZATION=0.95  # Blackwell управляет памятью эффективнее
```

### 3. Environment переменные

```bash
# .env.vllm для Blackwell
VLLM_GPU_MEMORY_UTILIZATION=0.95  # Blackwell: можно выше чем Ada (было 0.90)
VLLM_MAX_MODEL_LEN=16384          # Blackwell: больший контекст благодаря 96GB
VLLM_MAX_NUM_SEQS=512             # Blackwell: больше батчинга
VLLM_ENABLE_FP8=true              # NEW: FP8 precision
VLLM_USE_FLASHINFER=true          # NEW: FlashInfer attention
```

## 🎯 Рекомендуемые модели для Blackwell 96GB

### С FP8 квантизацией (рекомендуется)

| Модель | Базовая VRAM | С FP8 | Контекст | Tokens/sec |
|--------|--------------|-------|----------|------------|
| **Llama-3.1-70B-FP8** | ~140GB | **~70GB** ✅ | 16K | 200-300 |
| **Llama-3.1-405B-FP8** | ~810GB | **~200GB** | 8K | N/A (multi-GPU) |
| **Mixtral-8x22B-FP8** | ~280GB | **~140GB** | 32K | N/A (multi-GPU) |
| **Qwen2.5-72B-FP8** | ~144GB | **~72GB** ✅ | 32K | 180-250 |

### Без квантизации (FP16/BF16)

| Модель | VRAM | Контекст | Tokens/sec |
|--------|------|----------|------------|
| **Llama-3.1-8B** | ~16GB ✅ | 128K | 300-400 |
| **Llama-3.1-70B-AWQ** | ~40GB ✅ | 16K | 150-200 |
| **Mixtral-8x7B** | ~48GB ✅ | 32K | 200-280 |

### С MIG (Multi-Instance GPU)

```bash
# 2x 48GB instances для двух моделей Llama-70B-FP8
MIG_PROFILE=4g.48gb
MIG_INSTANCE_COUNT=2

# Или 4x 24GB для smaller models
MIG_PROFILE=2g.24gb
MIG_INSTANCE_COUNT=4
```

## ⚡ FP8 Precision на Blackwell

### Что такое FP8?

FP8 (8-bit floating point) - новый формат precision:
- **E4M3** - для активаций (4 бита экспонента, 3 мантисса)
- **E5M2** - для весов (5 бит экспонента, 2 мантисса)

### Преимущества на Blackwell

✅ **2x меньше памяти** чем FP16  
✅ **2x выше throughput** благодаря Tensor Cores 6-го поколения  
✅ **Минимальная потеря качества** (<1% difference vs FP16)  
✅ **Динамическое масштабирование** через Transformer Engine 2.0  
✅ **Больший batch size** и длинный контекст

### Включение FP8 в vLLM

```bash
# В .env.vllm
VLLM_ENABLE_FP8=true
VLLM_QUANTIZATION=fp8
VLLM_MODEL=neuralmagic/Meta-Llama-3.1-70B-Instruct-FP8

# Или динамическое FP8 (vLLM автоматически квантизует)
VLLM_ENABLE_FP8=true
VLLM_MODEL=meta-llama/Meta-Llama-3.1-70B-Instruct
```

### Запуск

```bash
docker-compose -f docker-compose.vllm.yml up -d

# Проверить логи
docker-compose -f docker-compose.vllm.yml logs -f vllm

# Должно быть:
# "FP8 computation enabled"
# "Tensor Engine: FP8"
```

## 📈 Производительность: Ada vs Blackwell

### Llama-3.1-70B (FP8)

| Метрика | RTX 6000 Ada | RTX 6000 Blackwell | Улучшение |
|---------|--------------|-------------------|-----------|
| **Tokens/sec** | N/A (не влезет) | 200-300 | ∞ |
| **TTFT** | N/A | 80-120ms | ∞ |
| **Throughput** | N/A | 40-60 req/s | ∞ |
| **Max batch** | N/A | 512 | ∞ |
| **Max context** | N/A | 16K | ∞ |

### Llama-3.1-8B (FP16)

| Метрика | RTX 6000 Ada | RTX 6000 Blackwell | Улучшение |
|---------|--------------|-------------------|-----------|
| **Tokens/sec** | 150-250 | 300-400 | **+60-100%** |
| **TTFT** | 100-300ms | 50-100ms | **-50%** |
| **Throughput** | 15-30 req/s | 40-80 req/s | **+167%** |
| **Max batch** | 256 | 512 | **+100%** |
| **Max context** | 8K | 128K | **+1500%** |

## 🔧 Продвинутые настройки

### 1. FlashInfer Attention

Blackwell поддерживает FlashInfer - оптимизированный attention:

```bash
# В .env.vllm
VLLM_USE_FLASHINFER=true

# Преимущества:
# - До 2x быстрее чем FlashAttention-2
# - Меньше использования памяти
# - Оптимизирован для длинных контекстов (>32K)
```

### 2. Chunked Prefill

Для длинных промптов:

```bash
VLLM_ENABLE_CHUNKED_PREFILL=true
VLLM_MAX_NUM_BATCHED_TOKENS=8192

# Позволяет обрабатывать длинные промпты эффективнее
```

### 3. Speculative Decoding

Ускорение генерации с draft моделью:

```bash
VLLM_SPECULATIVE_MODEL=meta-llama/Llama-3.1-8B-Instruct
VLLM_NUM_SPECULATIVE_TOKENS=5

# На Blackwell: до 2-3x ускорение для простых запросов
```

### 4. Multi-LoRA

Загрузка нескольких LoRA адаптеров:

```bash
VLLM_ENABLE_LORA=true
VLLM_MAX_LORAS=8

# Blackwell: до 8 LoRA адаптеров одновременно без overhead
```

## 🐛 Troubleshooting Blackwell

### Проблема: "CUDA capability sm_100 not supported"

```bash
# Обновить CUDA Toolkit
wget https://developer.download.nvidia.com/compute/cuda/12.6.0/local_installers/cuda_12.6.0_560.28.03_linux.run
sudo sh cuda_12.6.0_560.28.03_linux.run

# Или обновить Docker образ
docker pull nvidia/cuda:12.6.0-runtime-ubuntu22.04
```

### Проблема: vLLM не использует FP8

```bash
# Проверить логи
docker-compose -f docker-compose.vllm.yml logs vllm | grep FP8

# Если нет "FP8 computation enabled":
# 1. Проверить версию vLLM (должна быть 0.6.0+)
pip show vllm

# 2. Проверить модель поддерживает FP8
# Список моделей: https://huggingface.co/models?search=fp8

# 3. Явно указать квантизацию
VLLM_QUANTIZATION=fp8
```

### Проблема: Низкая производительность

```bash
# Проверить PCIe bandwidth
nvidia-smi nvlink --status

# Проверить memory bandwidth
nvidia-smi dmon -s m

# Включить persistence mode
sudo nvidia-smi -pm 1

# Установить максимальную частоту
sudo nvidia-smi -lgc 2550  # Max clock для Blackwell
```

## 📊 Мониторинг Blackwell

### Специфичные метрики

```bash
# FP8 utilization
nvidia-smi --query-gpu=utilization.gpu,utilization.memory,power.draw \
    --format=csv -l 1

# Tensor Core utilization
dcgmi stats -g 1 -e 1002,1003,1004

# Memory bandwidth utilization
nvidia-smi dmon -s m
```

### Оптимальные показатели

- **GPU Utilization:** 85-95%
- **Memory Utilization:** 90-95%
- **Power Draw:** 500-550W (TDP 600W)
- **Temperature:** 75-85°C
- **Memory Bandwidth:** >450GB/s (max 512GB/s)

## 🎯 Best Practices для Blackwell

1. **Используйте FP8** - основное преимущество Blackwell
2. **Увеличьте batch size** - Blackwell лучше справляется с батчингом
3. **Длинный контекст** - используйте 16K-128K tokens
4. **FlashInfer** - включайте для attention оптимизаций
5. **MIG** - для multiple workloads на одной GPU
6. **NVLink** - если multiple GPUs (до 1.8TB/s)

## 📚 Дополнительные ресурсы

- [NVIDIA Blackwell Architecture Whitepaper](https://www.nvidia.com/en-us/data-center/blackwell-architecture/)
- [vLLM Blackwell Optimizations](https://docs.vllm.ai/en/latest/performance/optimization.html)
- [FP8 Training Guide](https://docs.nvidia.com/deeplearning/transformer-engine/user-guide/examples/fp8_primer.html)
- [RTX 6000 Blackwell Spec](https://www.nvidia.com/en-us/design-visualization/rtx-6000/)

---

## 🎉 Итого

RTX 6000 Blackwell 96GB идеально подходит для vLLM:
- **2x быстрее** чем Ada Lovelace
- **Llama-70B с FP8** влезает в 96GB
- **До 400 tokens/sec** для Llama-8B
- **128K контекст** без проблем
- **MIG support** для multi-tenancy

