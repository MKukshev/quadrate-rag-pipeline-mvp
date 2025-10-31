# AnythingLLM Integration Guide

Руководство по интеграции AnythingLLM с вашим vLLM пайплайном.

## 🎯 Быстрый старт

### Настройка vLLM для AnythingLLM

Ваш vLLM контейнер предоставляет OpenAI-совместимый API, который AnythingLLM может использовать напрямую.

### Конфигурация LLM Provider в AnythingLLM

#### Одна модель (MEDIUM model)

```
LLM Provider: Generic OpenAI
Base URL: http://localhost:8001/v1
API Key: not-needed
Model Name: <your-model-name>
```

Например: `OpenGPT/gpt-oss-20b`, `meta-llama/Llama-2-13b-chat-hf`

#### Две модели одновременно

Если вы запустили `docker-compose.vllm-mig.yml` с dual models конфигурацией:

**MEDIUM model (большая модель, лучше для сложных задач):**
```
LLM Provider: Generic OpenAI
Base URL: http://localhost:8001/v1
API Key: not-needed
Model Name: <your-medium-model-name>
```

**SMALL model (быстрая модель, хороша для кода):**
```
LLM Provider: Generic OpenAI
Base URL: http://localhost:8002/v1
API Key: not-needed
Model Name: <your-small-model-name>
```

### Настройка Qdrant Vector Database в AnythingLLM

```
Vector Database: Qdrant
Qdrant API Endpoint: http://localhost:6333
API Key: (оставьте пустым)
```

## 🔧 Настройка через разные сети Docker

Если AnythingLLM и ваш пайплайн в разных Docker сетях:

### Вариант 1: Использовать IP адрес хоста

Узнайте IP адрес хоста:
```bash
# Linux/Mac
hostname -I | awk '{print $1}'

# или
ifconfig | grep "inet " | grep -v 127.0.0.1
```

Используйте в AnythingLLM:
```
Base URL: http://<HOST_IP>:8001/v1
Qdrant Endpoint: http://<HOST_IP>:6333
```

### Вариант 2: Объединить Docker сети

```bash
# Узнать имя сети вашего пайплайна
docker network ls

# Подключить AnythingLLM контейнер к этой сети
docker network connect <network_name> <anythingllm_container_name>

# Теперь можно использовать имена сервисов:
# vLLM: http://vllm-gpt:8001/v1
# Qdrant: http://qdrant:6333
```

## 🚀 Запуск пайплайна

### Одна модель
```bash
# Запуск
docker-compose -f docker-compose.vllm-mig.yml up -d

# Проверка
curl http://localhost:8001/health
curl http://localhost:6333/healthz
```

### Две модели одновременно
```bash
# Создайте .env.vllm-dual-models с конфигурацией обеих моделей
# См. DUAL_MODELS_QUICKSTART.md для деталей

# Запуск
make up-dual-models

# Проверка
make test-both-models
```

## 🧪 Проверка работоспособности

### Проверка vLLM

```bash
# Health check
curl http://localhost:8001/health

# Список моделей
curl http://localhost:8001/v1/models

# Тестовый запрос
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "OpenGPT/gpt-oss-20b",
    "messages": [{"role": "user", "content": "Hello!"}],
    "temperature": 0.7,
    "max_tokens": 100
  }'
```

### Проверка Qdrant

```bash
# Health check
curl http://localhost:6333/healthz

# Список коллекций
curl http://localhost:6333/collections

# Информация о кластере
curl http://localhost:6333/cluster
```

## 📊 Рекомендации по выбору модели

### MEDIUM model (порт 8001)
- ✅ **Лучше для:**
  - Сложных рассуждений и анализа
  - Работы с большими документами
  - Детальных ответов на сложные вопросы
  - Высокого качества генерации текста

- ❌ **Недостатки:**
  - Медленнее генерация (обычно ~30-50 tokens/sec)
  - Требует больше GPU памяти (обычно ~40-45 GB для ~20B параметров)
  - Выше latency первого токена (~500-800ms)

### SMALL model (порт 8002)
- ✅ **Лучше для:**
  - Быстрых ответов
  - Генерации кода
  - Простых инструкций
  - Высокой пропускной способности

- ❌ **Недостатки:**
  - Менее детальные ответы на сложные вопросы
  - Меньше параметров (обычно 7B vs 20B)

## 🔐 Безопасность

### Добавление API ключа для vLLM

Если нужно защитить vLLM API ключом, можно использовать nginx reverse proxy:

```nginx
location /v1 {
    if ($http_authorization != "Bearer your-secret-key") {
        return 401;
    }
    proxy_pass http://vllm:8001;
}
```

### Добавление API ключа для Qdrant

Обновите `docker-compose.vllm-mig.yml`:

```yaml
qdrant:
  environment:
    - QDRANT__SERVICE__API_KEY=your-secret-api-key-here
```

Используйте в AnythingLLM:
```
API Key: your-secret-api-key-here
```

## 🐛 Troubleshooting

### Проблема: AnythingLLM не может подключиться к vLLM

**Решение:**
1. Проверьте, что vLLM контейнер запущен: `docker ps | grep vllm`
2. Проверьте health endpoint: `curl http://localhost:8001/health`
3. Проверьте логи: `docker logs vllm-gpt-20b`
4. Убедитесь, что используете правильный URL с `/v1` на конце

### Проблема: AnythingLLM не может подключиться к Qdrant

**Решение:**
1. Проверьте, что Qdrant запущен: `docker ps | grep qdrant`
2. Проверьте health endpoint: `curl http://localhost:6333/healthz`
3. Убедитесь, что НЕ используете `/v1` в URL для Qdrant
4. Проверьте, нет ли API ключа в настройках Qdrant

### Проблема: Ошибка "Connection refused"

**Решение:**
1. Если AnythingLLM в Docker, используйте IP хоста вместо `localhost`
2. Проверьте firewall правила
3. Убедитесь, что порты не заняты: `netstat -an | grep 8001`

### Проблема: Медленная генерация

**Решение:**
1. Используйте SMALL model для быстрых ответов (порт 8002)
2. Уменьшите `max_tokens` в настройках AnythingLLM
3. Проверьте GPU утилизацию: `nvidia-smi`
4. Увеличьте `VLLM_MAX_NUM_SEQS` если есть свободная память

## 📚 Дополнительные ресурсы

- **Детальная настройка двух моделей:** См. `DUAL_MODELS_QUICKSTART.md`
- **MIG конфигурация:** См. `MIG_QUICKSTART.md`
- **vLLM документация:** https://docs.vllm.ai/
- **AnythingLLM документация:** https://docs.anythingllm.com/

## ❓ FAQ

**Q: Нужен ли API ключ для vLLM?**
A: Нет, vLLM по умолчанию не требует аутентификации. Можно указать любое значение (например, `not-needed`).

**Q: Можно ли использовать несколько workspace в AnythingLLM с одним Qdrant?**
A: Да, AnythingLLM создаёт отдельные коллекции для каждого workspace.

**Q: Конфликтует ли AnythingLLM с вашим backend?**
A: Нет, оба могут использовать один Qdrant инстанс. AnythingLLM создаёт свои коллекции с префиксом `anythingllm-`, а backend использует коллекцию `docs`.

**Q: Как переключаться между моделями в AnythingLLM?**
A: Добавьте обе модели как разные LLM Provider в настройках AnythingLLM и переключайтесь между ними по необходимости.

**Q: Сколько памяти нужно для обеих моделей?**
A: Зависит от конкретных моделей. Например, для ~20B модели требуется ~40-45 GB, для ~7B модели ~14-16 GB. Итого ~60 GB GPU памяти.

**Q: Можно ли запустить только одну модель?**
A: Да, закомментируйте один из vllm сервисов (`vllm-medium` или `vllm-small`) в `docker-compose.vllm-mig.yml` или используйте `make up-vllm-mig` для запуска только MEDIUM модели.

**Q: Какие модели можно использовать?**
A: Любые модели из HuggingFace, совместимые с vLLM. Укажите нужную модель в `VLLM_MODEL_MEDIUM` или `VLLM_MODEL_SMALL` переменных.

