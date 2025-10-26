# Обновление конфигурации GPU Backend

## ✅ Что изменено

### 1. Объединены Dockerfile
**Было:**
- `backend/Dockerfile` - CPU-only для Mac
- `backend/Dockerfile.gpu` - GPU для сервера
- `backend/Dockerfile.vllm` - vLLM сервис

**Стало:**
- `backend/Dockerfile` - CPU-only для Mac
- `backend/Dockerfile.vllm` - Универсальный GPU Dockerfile с CUDA 13.0

### 2. Dockerfile.vllm теперь универсальный

**Конфигурация:**
- **CUDA:** 13.0 (обновлено с 12.6)
- **Python:** 3.12 (обновлено с 3.11)
- **Ubuntu:** 24.04 (обновлено с 22.04)
- **PyTorch:** 2.7.0+ (обновлено с 2.5.0)
- **Зависимости:** Включает и vLLM, и backend deps

**Использование:**
- Для vLLM контейнера: запускает vLLM сервер (default CMD)
- Для backend контейнера: используется `command` override в docker-compose

### 3. Обновлены docker-compose файлы

**docker-compose.vllm.yml:**
```yaml
backend:
  build:
    dockerfile: backend/Dockerfile.vllm  # ← Использует тот же Dockerfile
  command: ["uvicorn", "backend.app:app", ...]
  volumes:
    - ./backend:/app/backend:ro  # ← Добавлено
```

**docker-compose.vllm-mig.yml:**
```yaml
backend:
  build:
    dockerfile: backend/Dockerfile.vllm  # ← Использует тот же Dockerfile
  command: ["uvicorn", "backend.app:app", ...]
  volumes:
    - ./backend:/app/backend:ro  # ← Добавлено
```

---

## 🎯 Результат

### Единый GPU образ

Один Dockerfile (`backend/Dockerfile.vllm`) используется для:
1. **vLLM контейнера** - запускает vLLM сервер
2. **Backend контейнера** - запускает FastAPI

### Преимущества

✅ Один образ = меньше дублирования  
✅ CUDA 13.0 + PyTorch 2.7.0 для всех GPU компонентов  
✅ Python 3.12  
✅ Все зависимости установлены один раз  
✅ Проще поддерживать

---

## 📊 Технические детали

### Dockerfile.vllm структура:

```dockerfile
FROM nvidia/cuda:13.0-devel-ubuntu24.04

# Python 3.12
# PyTorch 2.7.0+ (CUDA 13.0)
# vLLM 0.6.2
# Backend requirements
# Полный проект /app

# Default: запускает vLLM сервер
# Override: backend запускается через command в docker-compose
```

### Использование:

**Для vllm контейнера:**
```yaml
vllm:
  build:
    dockerfile: backend/Dockerfile.vllm
  # Использует default CMD → vLLM server
```

**Для backend контейнера:**
```yaml
backend:
  build:
    dockerfile: backend/Dockerfile.vllm
  command: ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
  # Override CMD → FastAPI backend
```

---

## 🚀 Использование

```bash
# Запуск на GPU сервере
make up-vllm

# Проверка
make check-gpu

# Backend использует тот же GPU образ
curl http://localhost:8000/health
```

---

## 📚 Документация

- [GPU_DEPLOYMENT_QUICKSTART.md](GPU_DEPLOYMENT_QUICKSTART.md)
- [docs/GPU_DEPLOYMENT_GUIDE.md](docs/GPU_DEPLOYMENT_GUIDE.md)
- [VLLM_QUICKSTART.md](VLLM_QUICKSTART.md)
