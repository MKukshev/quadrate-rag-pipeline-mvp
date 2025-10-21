# MIG Quick Start для RTX 6000 Blackwell 96GB

## 🚀 За 5 минут

### 1. Проверить GPU и MIG support
```bash
make list-mig
```

### 2. Настроить MIG (требуется sudo)
```bash
# Создать 2 инстанса по 40GB каждый
export MIG_PROFILE=3g.40gb
export MIG_INSTANCE_COUNT=2
make setup-mig
```

### 3. Обновить конфигурацию
```bash
# Скопировать MIG UUID из вывода предыдущей команды
nano .env.vllm-mig

# Установить:
MIG_DEVICE_UUID=MIG-GPU-xxxxx/3/0  # Ваш UUID
HUGGING_FACE_HUB_TOKEN=hf_xxxxx    # Ваш токен
```

### 4. Запустить vLLM с MIG
```bash
make up-vllm-mig
```

### 5. Проверить
```bash
make logs-vllm-mig
curl http://localhost:8000/health
```

## 📊 MIG Profiles

| Profile | VRAM | Instances | Модели |
|---------|------|-----------|--------|
| 1g.12gb | 12GB | до 7 | Llama-8B |
| 2g.24gb | 24GB | до 3 | Llama-13B |
| **3g.40gb** ✅ | 40GB | до 2 | Llama-70B (AWQ) |
| 4g.48gb | 48GB | 1+1 | Llama-70B (GPTQ) |
| 7g.96gb | 96GB | 1 | Full GPU |

**Рекомендуется:** `3g.40gb` для баланса производительности и гибкости

## 🔄 Отключить MIG

```bash
sudo nvidia-smi -i 0 -mig 0
sudo nvidia-smi -i 0 -r
```

## 📚 Полная документация

См. [docs/MIG_SETUP_GUIDE.md](docs/MIG_SETUP_GUIDE.md)

