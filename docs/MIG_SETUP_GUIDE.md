# NVIDIA MIG Setup Guide для RTX 6000 Blackwell 96GB

## 🎯 Что такое MIG?

**MIG (Multi-Instance GPU)** — технология NVIDIA, позволяющая разбить одну физическую GPU на несколько изолированных виртуальных GPU (инстансов).

### Преимущества MIG для vLLM

✅ **Изоляция ресурсов** - каждый инстанс имеет гарантированную память и вычислительные ресурсы  
✅ **Повышение утилизации** - запуск нескольких моделей одновременно на одной GPU  
✅ **QoS (Quality of Service)** - предсказуемая производительность для каждого инстанса  
✅ **Безопасность** - изоляция на уровне hardware между инстансами  
✅ **Гибкость** - разные модели с разными требованиями к памяти

## 📊 MIG Profiles для RTX 6000 Blackwell 96GB

| Profile | VRAM | Compute | Max Instances | Рекомендуемые модели |
|---------|------|---------|---------------|---------------------|
| **1g.12gb** | 12GB | 1/7 GPU | 7 | Llama-3.1-8B, Mistral-7B |
| **2g.24gb** | 24GB | 2/7 GPU | 3 | Llama-3.1-13B, Mixtral-8x7B (quant) |
| **3g.40gb** | 40GB | 3/7 GPU | 2 | Llama-3.1-70B (AWQ), Qwen-72B (AWQ) |
| **4g.48gb** | 48GB | 4/7 GPU | 1+1 | Llama-3.1-70B (GPTQ) |
| **7g.96gb** | 96GB | Full GPU | 1 | Llama-3.1-405B (quant), без разделения |

## 🚀 Быстрый старт

### Шаг 1: Проверка поддержки MIG

```bash
# Проверить GPU
nvidia-smi -L

# Проверить возможности MIG
nvidia-smi --query-gpu=mig.mode.current --format=csv

# Посмотреть доступные MIG устройства
./scripts/list_mig_devices.sh
```

### Шаг 2: Настройка MIG профиля

```bash
# Редактировать конфигурацию
nano .env.vllm-mig

# Установить профиль (например, 3g.40gb для 2 инстансов по 40GB)
MIG_PROFILE=3g.40gb
MIG_INSTANCE_COUNT=2
```

### Шаг 3: Создание MIG инстансов

```bash
# Запустить скрипт настройки MIG (требуется sudo)
sudo ./scripts/setup_mig.sh

# Или с кастомными параметрами
sudo MIG_PROFILE=3g.40gb MIG_INSTANCE_COUNT=2 ./scripts/setup_mig.sh
```

### Шаг 4: Получить UUID MIG устройства

```bash
# Список MIG устройств
nvidia-smi -L | grep MIG

# Пример вывода:
# GPU 0: MIG-12345678-90ab-cdef-1234-567890abcdef (UUID: MIG-GPU-xxx/3/0)
```

### Шаг 5: Обновить конфигурацию

```bash
# Скопировать UUID из предыдущего шага
nano .env.vllm-mig

# Обновить:
MIG_DEVICE_UUID=MIG-GPU-12345678-1234-1234-1234-123456789abc/3/0
```

### Шаг 6: Запустить vLLM с MIG

```bash
# Запустить с MIG конфигурацией
docker-compose -f docker-compose.vllm-mig.yml up -d

# Проверить логи
docker-compose -f docker-compose.vllm-mig.yml logs -f vllm
```

## 📝 Примеры конфигураций

### Конфигурация 1: Максимальная параллельность (7 инстансов)

**Use case:** Много небольших моделей одновременно

```bash
# .env.vllm-mig
MIG_PROFILE=1g.12gb
MIG_INSTANCE_COUNT=7
VLLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
VLLM_GPU_MEMORY_UTILIZATION=0.95
VLLM_MAX_MODEL_LEN=4096
VLLM_MAX_NUM_SEQS=64
```

**Результат:** 7 изолированных vLLM инстансов, каждый с Llama-3.1-8B

**Команды:**
```bash
# Создать 7 MIG инстансов
sudo MIG_PROFILE=1g.12gb MIG_INSTANCE_COUNT=7 ./scripts/setup_mig.sh

# Запустить vLLM на первом инстансе
MIG_DEVICE_UUID=$(nvidia-smi -L | grep MIG | head -1 | grep -oP 'MIG-[a-f0-9-]+')
docker-compose -f docker-compose.vllm-mig.yml up -d
```

### Конфигурация 2: Баланс производительности (2 инстанса)

**Use case:** 2 большие модели с хорошей производительностью

```bash
# .env.vllm-mig
MIG_PROFILE=3g.40gb
MIG_INSTANCE_COUNT=2
VLLM_MODEL=meta-llama/Meta-Llama-3.1-70B-Instruct-AWQ
VLLM_GPU_MEMORY_UTILIZATION=0.95
VLLM_MAX_MODEL_LEN=8192
VLLM_MAX_NUM_SEQS=128
```

**Результат:** 2 инстанса по 40GB для моделей 70B с квантизацией

### Конфигурация 3: Dev + Prod (смешанная)

**Use case:** Один инстанс для production, остальные для разработки

```bash
# Production инстанс: 4g.48gb (48GB)
MIG_PROFILE=4g.48gb
MIG_INSTANCE_COUNT=1

# Затем создать еще инстансы для dev
MIG_PROFILE=3g.40gb
MIG_INSTANCE_COUNT=1
```

## 🔧 Детальная настройка

### Создание кастомной конфигурации MIG

```bash
#!/bin/bash
# Пример: 1x48GB (prod) + 2x24GB (dev)

# Enable MIG
sudo nvidia-smi -i 0 -mig 1
sudo nvidia-smi -i 0 -r

# Create 48GB instance for production
sudo nvidia-smi mig -i 0 -cgi 4g.48gb -C

# Create 24GB instances for development
sudo nvidia-smi mig -i 0 -cgi 2g.24gb -C
sudo nvidia-smi mig -i 0 -cgi 2g.24gb -C

# List created instances
nvidia-smi mig -lgi
```

### Запуск нескольких vLLM на разных MIG инстансах

```bash
# Получить список MIG UUIDs
nvidia-smi -L | grep MIG

# Запустить vLLM #1 на порту 8001
export MIG_DEVICE_UUID=MIG-GPU-xxx/3/0
docker-compose -f docker-compose.vllm-mig.yml up -d

# Запустить vLLM #2 на порту 8002 (другой MIG instance)
# В docker-compose.vllm-mig.yml изменить ports на 8002:8001
export MIG_DEVICE_UUID=MIG-GPU-xxx/4/0
docker-compose -f docker-compose.vllm-mig.yml -p vllm2 up -d
```

## 📊 Мониторинг MIG инстансов

### Проверка использования GPU

```bash
# Общая информация
nvidia-smi

# Детали по MIG инстансам
nvidia-smi mig -lgi

# Мониторинг в реальном времени
watch -n 1 nvidia-smi
```

### Метрики производительности

```bash
# Utilization каждого MIG инстанса
nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total \
    --format=csv,noheader -l 1

# Специфично для MIG
nvidia-smi mig -i 0 -lgi --format=csv
```

## 🔄 Управление MIG

### Отключение MIG и возврат к full GPU

```bash
# Удалить все MIG инстансы
sudo nvidia-smi mig -i 0 -dci
sudo nvidia-smi mig -i 0 -dgi

# Отключить MIG mode
sudo nvidia-smi -i 0 -mig 0

# Перезагрузить GPU
sudo nvidia-smi -i 0 -r
```

### Изменение конфигурации MIG

```bash
# 1. Остановить контейнеры
docker-compose -f docker-compose.vllm-mig.yml down

# 2. Удалить текущие MIG инстансы
sudo nvidia-smi mig -i 0 -dci
sudo nvidia-smi mig -i 0 -dgi

# 3. Создать новые с другим профилем
sudo MIG_PROFILE=2g.24gb MIG_INSTANCE_COUNT=3 ./scripts/setup_mig.sh

# 4. Обновить .env и перезапустить
docker-compose -f docker-compose.vllm-mig.yml up -d
```

## 🐛 Troubleshooting

### Проблема: "MIG mode change failed"

```bash
# Убедитесь что нет активных процессов на GPU
sudo fuser -v /dev/nvidia0
sudo kill -9 <PID>

# Перезагрузите GPU
sudo nvidia-smi -i 0 -r

# Попробуйте снова
sudo nvidia-smi -i 0 -mig 1
```

### Проблема: "Insufficient resources"

```bash
# Проверить сколько доступно памяти
nvidia-smi --query-gpu=memory.free --format=csv

# Удалить все MIG инстансы и начать заново
sudo nvidia-smi mig -i 0 -dci
sudo nvidia-smi mig -i 0 -dgi

# Создать меньше/меньшие инстансы
sudo MIG_PROFILE=1g.12gb MIG_INSTANCE_COUNT=4 ./scripts/setup_mig.sh
```

### Проблема: Docker не видит MIG device

```bash
# Убедитесь что NVIDIA Container Toolkit установлен
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# Проверить device UUID правильный
nvidia-smi -L | grep MIG

# Обновить MIG_DEVICE_UUID в .env.vllm-mig
```

### Проблема: vLLM OOM на MIG instance

```bash
# Уменьшить параметры в .env.vllm-mig:
VLLM_GPU_MEMORY_UTILIZATION=0.85  # Было 0.95
VLLM_MAX_MODEL_LEN=4096           # Было 8192
VLLM_MAX_NUM_SEQS=64              # Было 128

# Или использовать квантизованную модель
VLLM_MODEL=TheBloke/Llama-2-70B-Chat-AWQ
```

## 📈 Рекомендации по производительности

### Оптимальные конфигурации

**Для высокого throughput (много запросов):**
```bash
MIG_PROFILE=1g.12gb
MIG_INSTANCE_COUNT=7
# 7 параллельных инстансов Llama-8B
# Throughput: ~150-200 requests/sec суммарно
```

**Для низкой latency (быстрые ответы):**
```bash
MIG_PROFILE=3g.40gb
MIG_INSTANCE_COUNT=2
# 2 мощных инстанса с большим кэшем
# Latency: 50-100ms для first token
```

**Для смешанной нагрузки:**
```bash
# 1x 4g.48gb для prod (Llama-70B-AWQ)
# 1x 3g.40gb для staging
# Остаток под dev/test
```

## 🔐 Best Practices

1. **Планируйте заранее** - определите требования к моделям перед созданием MIG
2. **Мониторинг** - следите за утилизацией каждого инстанса
3. **Тестирование** - проверьте производительность перед production
4. **Документирование** - записывайте какие инстансы для чего используются
5. **Backup конфигурации** - сохраните рабочие MIG настройки

## 📚 Полезные команды

```bash
# Список всех MIG команд
nvidia-smi mig --help

# Профили для конкретной GPU
nvidia-smi mig -lgip

# Детальная информация о MIG instances
nvidia-smi mig -lgi --format=csv

# Экспорт конфигурации
nvidia-smi mig -lgi > mig_config_backup.txt
```

## 🔗 Дополнительные ресурсы

- [NVIDIA MIG User Guide](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/)
- [vLLM Multi-GPU Documentation](https://docs.vllm.ai/en/latest/serving/distributed_serving.html)
- [Docker + MIG Best Practices](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/mig.html)

---

## 🎉 Готово!

Теперь вы можете эффективно использовать RTX 6000 Blackwell 96GB с MIG для запуска нескольких vLLM инстансов!

