# LLM_MAX_TOKENS - Объяснение параметра

## 📋 TL;DR

**`LLM_MAX_TOKENS`** - это максимальное количество токенов в **ОТВЕТЕ** модели (output).

**Используется в ОБЕИХ конфигурациях: Ollama и vLLM!**

---

## 🔍 Где используется

### 1. В config.py (определение)

```python
# backend/services/config.py
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "256"))
```

**Default:** 256 токенов (очень мало!)

---

### 2. Для Ollama (rag.py)

```python
# backend/services/rag.py

def call_llm(prompt: str) -> str:
    if LLM_MODE == "ollama":
        r = requests.post(
            "http://ollama:11434/api/generate",
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "options": {
                    "num_predict": LLM_MAX_TOKENS,  # ← Используется здесь!
                    "num_ctx": OLLAMA_NUM_CTX,
                },
            },
            ...
        )
```

**Параметр Ollama API:**
- **`num_predict`** - максимальное количество токенов в генерируемом ответе
- Аналог `max_tokens` в других API

---

### 3. Для vLLM (rag_vllm.py)

```python
# backend/services/rag_vllm.py

def call_vllm(prompt: str, model: Optional[str] = None, **kwargs) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": kwargs.get("max_tokens", config.LLM_MAX_TOKENS),  # ← Используется здесь!
        "temperature": ...,
    }
    
    response = requests.post(f"{VLLM_URL}/chat/completions", json=payload)
```

**Параметр vLLM OpenAI-compatible API:**
- **`max_tokens`** - максимальное количество токенов в ответе
- Стандартный параметр OpenAI API

---

## 📊 Два разных параметра!

### НЕ ПУТАТЬ:

| Что | Параметр | Для чего |
|-----|----------|----------|
| **Размер ответа (output)** | `LLM_MAX_TOKENS` | Максимум токенов в ответе LLM |
| **Размер контекста (input)** | `OLLAMA_NUM_CTX` или `VLLM_MAX_MODEL_LEN` | Размер контекстного окна |

### Для Ollama:

```yaml
# docker-compose.yml
environment:
  - LLM_MODEL=llama3.1:8b
  - OLLAMA_NUM_CTX=40960      # ← INPUT: Контекстное окно (что можем отправить)
  - LLM_MAX_TOKENS=2048        # ← OUTPUT: Максимум в ответе (что получим)
```

**В API запросе:**
```json
{
  "options": {
    "num_ctx": 40960,      // Размер контекста (input)
    "num_predict": 2048    // Размер ответа (output)
  }
}
```

### Для vLLM:

```yaml
# docker-compose.vllm-mig.yml
vllm-medium:
  environment:
    - VLLM_MODEL=openai/gpt-oss-20b
    - VLLM_MAX_MODEL_LEN=8192  # ← INPUT: Контекстное окно сервера

backend:
  environment:
    - LLM_MAX_TOKENS=512       # ← OUTPUT: Максимум в ответе
```

**В API запросе:**
```json
{
  "max_tokens": 512      // Размер ответа (output)
}
```

---

## 🎯 Зачем ограничивать ответ?

### Причины использования LLM_MAX_TOKENS:

1. **Контроль стоимости** (для облачных моделей)
   - Меньше токенов = меньше платим

2. **Скорость генерации**
   - 256 токенов генерируется быстрее чем 2048

3. **Краткие ответы**
   - Для RAG достаточно 256-512 токенов
   - Суммаризация требует больше (1000-2048)

4. **Предсказуемость**
   - Модель не будет генерировать слишком длинные ответы

---

## ⚙️ Рекомендуемые значения

### Для RAG (/ask endpoint):

```bash
LLM_MAX_TOKENS=512   # Достаточно для большинства ответов
```

### Для Суммаризации (/summarize):

```bash
LLM_MAX_TOKENS=2048  # Нужно больше для полного summary
```

### Для длинных ответов:

```bash
LLM_MAX_TOKENS=4096  # Для развёрнутых объяснений
```

---

## 🔧 Проблема в текущей конфигурации

### Было:

```yaml
# docker-compose.yml (старое)
- LLM_TIMEOUT=240
- CHUNK_TOKENS=500
- CHUNK_OVERLAP=50

# config.py (default)
LLM_MAX_TOKENS = 256  # ← Слишком мало!
```

**Проблема:** 256 токенов недостаточно для summary!

### Исправлено:

```yaml
# docker-compose.yml (новое)
- LLM_MAX_TOKENS=${LLM_MAX_TOKENS:-2048}  # ← Теперь 2048
- LLM_TIMEOUT=300
```

---

## 📖 Примеры

### Пример 1: RAG ответ (256 токенов)

**Запрос:**
```bash
curl -X POST /ask -d '{"q":"Какой бюджет проекта?"}'
```

**Ответ (256 токенов):**
```
Based on the context, Project Alpha has a budget of $200,000.
This budget was established at the start of the project on March 1, 2025.
```

**Размер:** ~30 токенов (в пределах лимита 256)

### Пример 2: Суммаризация (нужно > 256)

**Запрос:**
```bash
curl -X POST /summarize -d '{"doc_id":"..."}'
```

**Ответ (нужно ~500-1000 токенов):**
```
**Summary of Project Alpha**

Project Alpha, initiated on 1 March 2025, is a $200,000 initiative...
[полный summary продолжается...]

**Team**
The project involves 5 engineers: Alice (team lead), Bob (backend)...

**Technologies**
Backend: Python + FastAPI
Frontend: React + TypeScript
...
```

**Размер:** ~500-1000 токенов

**С лимитом 256:** Обрежется на середине! ❌  
**С лимитом 2048:** Полный ответ ✅

---

## 🔄 Сравнение Ollama vs vLLM

| Аспект | Ollama | vLLM |
|--------|--------|------|
| **API параметр для max output** | `num_predict` | `max_tokens` |
| **Backend переменная** | `LLM_MAX_TOKENS` | `LLM_MAX_TOKENS` |
| **Где устанавливается** | При каждом вызове API | При каждом вызове API |
| **Default в config.py** | 256 | 256 |
| **Рекомендуемое для summary** | 2048 | 2048 |

---

## ✅ Итоговая конфигурация

### Для Ollama

```yaml
# docker-compose.yml
environment:
  - LLM_MODEL=llama3.1:8b
  
  # INPUT parameters (что можем отправить)
  - OLLAMA_NUM_CTX=8192         # Размер контекстного окна
  
  # OUTPUT parameters (что получим)
  - LLM_MAX_TOKENS=2048         # Максимум токенов в ответе
  - LLM_TIMEOUT=300             # Таймаут на генерацию
```

### Для vLLM

```yaml
# docker-compose.vllm-mig.yml

# vLLM server
vllm-medium:
  environment:
    - VLLM_MODEL=openai/gpt-oss-20b
    - VLLM_MAX_MODEL_LEN=8192   # INPUT: Размер контекста сервера

# Backend
backend:
  environment:
    - LLM_MODE=vllm
    - LLM_MAX_TOKENS=512        # OUTPUT: Максимум в ответе
    - LLM_TIMEOUT=120
```

---

## 🎯 Вывод

**`LLM_MAX_TOKENS` - это параметр OUTPUT (ответа модели), используется ОДИНАКОВО для Ollama и vLLM!**

**Для контроля INPUT (контекстного окна) используются разные параметры:**
- Ollama: `OLLAMA_NUM_CTX`
- vLLM: `VLLM_MAX_MODEL_LEN`

**Для суммаризации нужно увеличить `LLM_MAX_TOKENS` до 2048!** ✅

