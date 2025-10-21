# Руководство: Режимы работы /ask endpoint

## 🎯 Обзор

Endpoint `/ask` теперь поддерживает 4 режима работы для гибкого контроля суммаризации.

---

## 📋 Режимы работы

### 1. `mode: "auto"` (по умолчанию) ⭐

**Поведение:** Система автоматически решает нужна ли суммаризация

**Алгоритм:**
```python
if context_tokens > model.summarization_threshold:
    use_summarization = True
else:
    use_summarization = False
```

**Когда использовать:**
- ✅ Обычные вопросы
- ✅ Доверяете системе
- ✅ Не уверены нужна ли суммаризация

**Пример:**
```bash
curl -X POST http://localhost:8000/ask \
  -d '{"q":"migration projects","space_id":"demo"}' | jq
```

**Response:**
```json
{
  "answer": "...",
  "mode": "auto",
  "summarized": true,  // или false, в зависимости от context size
  "context_tokens": 5000
}
```

---

### 2. `mode: "normal"` 

**Поведение:** Обычный RAG без суммаризации, независимо от размера контекста

**Алгоритм:**
```python
use_summarization = False  # Всегда
```

**Когда использовать:**
- ✅ Нужны все детали
- ✅ Точные цитаты важны
- ✅ Контекст не слишком большой

**Пример:**
```bash
curl -X POST http://localhost:8000/ask \
  -d '{"q":"list all deadlines","mode":"normal","top_k":15}' | jq
```

**Response:**
```json
{
  "answer": "Project A: June 1, Project B: July 15, Project C: August 30...",
  "mode": "normal",
  "summarized": false,
  "context_tokens": 4500
}
```

---

### 3. `mode: "summarize"` 

**Поведение:** Принудительная суммаризация, даже для малого контекста

**Алгоритм:**
```python
use_summarization = True  # Всегда
```

**Когда использовать:**
- ✅ "Дай краткий обзор..."
- ✅ "TL;DR всех документов..."
- ✅ Dashboard / overview
- ✅ Быстрый ответ важнее деталей

**Пример:**
```bash
curl -X POST http://localhost:8000/ask \
  -d '{"q":"overview of all projects","mode":"summarize","top_k":30}' | jq
```

**Response:**
```json
{
  "answer": "Found 5 projects: 3 in planning, 2 in execution. Total budget: $800K.",
  "mode": "summarize",
  "summarized": true,
  "context_tokens": 8000
}
```

---

### 4. `mode: "detailed"` 

**Поведение:** Максимально детальный ответ, без суммаризации

**Алгоритм:**
```python
use_summarization = False  # Всегда
# То же что "normal", но семантически означает "хочу все детали"
```

**Когда использовать:**
- ✅ "Перечисли ВСЕ..."
- ✅ "Дай полный список..."
- ✅ Аналитические запросы
- ✅ Нужна максимальная точность

**Пример:**
```bash
curl -X POST http://localhost:8000/ask \
  -d '{"q":"list ALL project details with dates and budgets","mode":"detailed","top_k":50}' | jq
```

**Response:**
```json
{
  "answer": "Project Alpha: Started March 1, 2025, Budget $200K, Team: John (lead), Alice (dev), Bob (qa)... [полные детали всех проектов]",
  "mode": "detailed",
  "summarized": false,
  "context_tokens": 12000
}
```

---

## 📊 Сравнение режимов

| Режим | Суммаризация | Когда | Use Case |
|-------|--------------|-------|----------|
| **auto** | Если context > threshold | Не уверены | Обычные вопросы |
| **normal** | Никогда | Нужны детали | Точные данные |
| **summarize** | Всегда | Нужен overview | Dashboard, быстрый обзор |
| **detailed** | Никогда | Нужно ВСЁ | Аналитика, исчерпывающий ответ |

---

## 🔍 Матрица решений

### Для пользователей

```
Какой вопрос задаете?
    │
    ├─ "Дай краткий обзор..." → mode: "summarize"
    │
    ├─ "Перечисли ВСЕ..." → mode: "detailed"
    │
    ├─ "Что такое X?" → mode: "normal"
    │
    └─ Не уверен → mode: "auto" (default)
```

### Для фронтенда

```
UI Element           Mode
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Regular chat         "auto"
Quick answer button  "summarize"
Detailed view        "detailed"
Analytics panel      "normal"
```

---

## 🎨 Frontend примеры

### React компонент с выбором режима

```typescript
import { useState } from 'react';

function ChatInterface() {
  const [mode, setMode] = useState<'auto' | 'normal' | 'summarize' | 'detailed'>('auto');
  const [question, setQuestion] = useState('');
  
  async function ask() {
    const response = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        q: question,
        space_id: workspace.id,
        mode: mode,
        top_k: 10
      })
    });
    
    const data = await response.json();
    
    // Показать индикатор если была суммаризация
    if (data.summarized) {
      showBadge(`📄 Summarized from ${data.context_tokens} tokens`);
    }
    
    return data.answer;
  }
  
  return (
    <div>
      {/* Mode selector */}
      <div className="mode-tabs">
        <button 
          className={mode === 'auto' ? 'active' : ''}
          onClick={() => setMode('auto')}
        >
          🤖 Smart
        </button>
        <button 
          className={mode === 'summarize' ? 'active' : ''}
          onClick={() => setMode('summarize')}
        >
          📄 Brief
        </button>
        <button 
          className={mode === 'detailed' ? 'active' : ''}
          onClick={() => setMode('detailed')}
        >
          📋 Detailed
        </button>
      </div>
      
      {/* Question input */}
      <textarea 
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask a question..."
      />
      
      <button onClick={ask}>Ask</button>
    </div>
  );
}
```

### Умные подсказки в UI

```typescript
// Автоматические подсказки на основе вопроса
function suggestMode(question: string): string {
  const lower = question.toLowerCase();
  
  if (lower.includes('overview') || lower.includes('краткий') || lower.includes('обзор')) {
    return 'summarize';
  }
  
  if (lower.includes('all') || lower.includes('все') || lower.includes('list')) {
    return 'detailed';
  }
  
  return 'auto';
}

// Использование
const suggestedMode = suggestMode(userQuestion);
if (suggestedMode !== mode) {
  showHint(`Suggested mode: ${suggestedMode}`);
}
```

---

## 📝 Примеры запросов

### Один вопрос - разные режимы

**Вопрос:** "Tell me about cloud migration projects"

#### Mode: auto
```bash
curl -d '{"q":"cloud migration projects","mode":"auto","top_k":10}'
```
**Ответ:** Умное решение (суммаризация если контекст > 3K)

#### Mode: summarize
```bash
curl -d '{"q":"cloud migration projects","mode":"summarize","top_k":10}'
```
**Ответ:** "3 projects: Cloud (Q2, $200K), Data (Q3, $150K), App (Q4, $100K)"

#### Mode: detailed
```bash
curl -d '{"q":"cloud migration projects","mode":"detailed","top_k":10}'
```
**Ответ:** "Cloud Migration Project: Start date March 1, 2025. Budget $200,000 allocated. Team composition: 5 senior engineers (John Smith - lead, Alice Johnson - backend, ...). Technology stack: Kubernetes 1.28, AWS EKS, PostgreSQL 15..."

---

## 🔧 Логи для debugging

### Console output примеры

#### Auto mode с малым контекстом
```
[RAG] Mode: auto. Context 1500 tokens ≤ threshold 3000. Using normal RAG.
```

#### Auto mode с большим контекстом
```
[RAG] Mode: auto. Context 5000 tokens > threshold 3000. Using summarization.
[Summarization] Document is large (5000 tokens). Starting Map-Reduce...
[Summarization] Split into 1 chunks
[Summarization] Processing chunk 1/1...
[Summarization] MAP phase complete. Generated 1 summaries
[Summarization] REDUCE phase: Combined summary is 1200 tokens
[Summarization] Complete!
```

#### Summarize mode (forced)
```
[RAG] Mode: summarize (forced). Context: 2000 tokens
[Summarization] Processing...
```

#### Detailed mode
```
[RAG] Mode: detailed (no summarization). Context: 8000 tokens
```

#### Invalid mode (graceful handling)
```
[RAG] Invalid mode 'wrong_mode', using default 'auto'
[RAG] Mode: auto. Context 3500 tokens > threshold 3000. Using summarization.
```

---

## 🎯 Best Practices

### Когда использовать каждый режим

#### `auto` - 80% случаев
```typescript
// Обычные вопросы
await ask("What is X?", mode: "auto")
await ask("When is the deadline?", mode: "auto")
```

#### `summarize` - Dashboards, overviews
```typescript
// Dashboard карточка "Quick Summary"
const summary = await ask(
  "Summarize all Q4 projects",
  mode: "summarize",
  top_k: 50
);
```

#### `detailed` - Analytics, reports
```typescript
// Аналитический отчет
const details = await ask(
  "List all projects with budgets, teams, and timelines",
  mode: "detailed",
  top_k: 100
);
```

#### `normal` - Стандартный RAG
```typescript
// Когда знаете что контекст небольшой
const answer = await ask(
  "Who is the project manager?",
  mode: "normal",
  top_k: 3
);
```

---

## 📊 Performance по режимам

| Режим | Context | LLM calls | Time | Tokens used |
|-------|---------|-----------|------|-------------|
| **auto** (small) | 1500 | 1 | 3s | 2000 |
| **auto** (large) | 6000 | 2-4 | 15s | 3500 (summarized) |
| **normal** | Any | 1 | 3s | Full context |
| **summarize** | Any | 2-4 | 15s | Summarized |
| **detailed** | Any | 1 | 3s | Full context |

---

## 🧪 Тестирование

```bash
# Тест всех режимов
QUESTION="Tell me about all migration projects"
SPACE="demo"

# Auto mode
curl -X POST http://localhost:8000/ask \
  -d "{\"q\":\"$QUESTION\",\"space_id\":\"$SPACE\",\"mode\":\"auto\"}" | \
  jq '{mode, summarized, context_tokens}'

# Normal mode
curl -X POST http://localhost:8000/ask \
  -d "{\"q\":\"$QUESTION\",\"space_id\":\"$SPACE\",\"mode\":\"normal\"}" | \
  jq '{mode, summarized}'

# Summarize mode
curl -X POST http://localhost:8000/ask \
  -d "{\"q\":\"$QUESTION\",\"space_id\":\"$SPACE\",\"mode\":\"summarize\"}" | \
  jq '{mode, summarized}'

# Detailed mode
curl -X POST http://localhost:8000/ask \
  -d "{\"q\":\"$QUESTION\",\"space_id\":\"$SPACE\",\"mode\":\"detailed\"}" | \
  jq '{mode, summarized}'
```

---

## 📚 API Reference

### Request

```json
{
  "q": "Your question",
  "space_id": "demo",
  "top_k": 10,
  "doc_types": ["technical_docs"],
  "mode": "auto"  // NEW: "auto" | "normal" | "summarize" | "detailed"
}
```

### Response

```json
{
  "answer": "Answer text...",
  "sources": [...],
  "summarized": true,      // Была ли использована суммаризация
  "context_tokens": 5000,  // Размер исходного контекста
  "mode": "auto",          // Использованный режим
  "model": "llama3.1:8b"   // Модель LLM
}
```

---

## 🎉 Готово!

Теперь у вас полный контроль над суммаризацией через параметр `mode`.

**Встроенные режимы:**
- ✅ `auto` - умное автоматическое решение
- ✅ `normal` - стандартный RAG
- ✅ `summarize` - всегда краткий overview
- ✅ `detailed` - все детали без суммаризации

**Features:**
- Валидация с fallback на default
- Подробные логи для debugging
- Прозрачность через response fields

