# vLLM Quick Start для RTX 6000 Blackwell 96GB

## 🚀 Быстрый запуск (3 команды)

```bash
# 1. Скопировать конфигурацию vLLM
cp .env.vllm .env

# 2. Добавить HuggingFace токен в .env
nano .env  # HUGGING_FACE_HUB_TOKEN=hf_xxxxx

# 3. Запустить
make up-vllm
```

## 📊 Что получите

- ⚡ **150-250 tokens/sec** (vs 40-60 на Ollama)
- 🚀 **15-30 requests/sec** throughput
- ⏱️ **0.1-0.3s** first token latency
- 💾 Эффективное использование 96GB VRAM

## 🔄 Переключение между Ollama и vLLM

```bash
# Переключиться на vLLM (GPU)
make switch-vllm

# Вернуться к Ollama (CPU/GPU)
make switch-ollama
```

## 🎯 Поддерживаемые модели на RTX 6000 96GB

| Модель | VRAM | Параметры |
|--------|------|-----------|
| Llama-3.1-8B ✅ | 16GB | Рекомендуется |
| Llama-3.1-70B | 80GB | Макс качество |
| Mistral-7B | 14GB | Быстрая |
| Mixtral-8x7B | 90GB | Длинный контекст |

## 📝 Изменение модели

Отредактируйте в `.env.vllm`:
```bash
VLLM_MODEL=mistralai/Mistral-7B-Instruct-v0.2
```

Перезапустите:
```bash
make down-vllm && make up-vllm
```

## 📚 Полная документация

См. [docs/VLLM_DEPLOYMENT.md](docs/VLLM_DEPLOYMENT.md)

