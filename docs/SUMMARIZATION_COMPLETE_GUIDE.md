# Полное руководство по суммаризации в RAG-пайплайне

## 📋 Содержание

1. [Обзор системы](#обзор-системы)
2. [Паттерн 1: Прямая суммаризация](#паттерн-1-прямая-суммаризация)
3. [Паттерн 2: Smart Context Compression](#паттерн-2-smart-context-compression)
4. [Паттерн 3: Режимы работы](#паттерн-3-режимы-работы)
5. [Паттерн 4: Предвычисленные summaries](#паттерн-4-предвычисленные-summaries)
6. [Паттерн 5: Потоковая суммаризация](#паттерн-5-потоковая-суммаризация)
7. [Паттерн 6: Суммаризация тредов](#паттерн-6-суммаризация-тредов)
8. [Архитектура системы](#архитектура-системы)
9. [Интеграция и использование](#интеграция-и-использование)

---

## Обзор системы

### Зачем нужна суммаризация в RAG?

**Проблемы без суммаризации:**
- Большие документы не умещаются в context window LLM
- Пользователь получает фрагменты вместо целостной картины
- Невозможно быстро понять содержание документа
- Повторные запросы генерируют один и тот же summary

**Решения:**
1. **Map-Reduce** для больших документов
2. **Адаптивная** суммаризация под модель LLM
3. **Режимы** для разных use cases
4. **Кэширование** для скорости
5. **Streaming** для UX
6. **Структурированная** обработка тредов

### Компоненты системы

```
backend/services/
├── summarization.py           # Основная логика (Patterns 1, 2, 5)
├── llm_config.py             # Конфигурация моделей (Pattern 2)
├── summary_store.py          # Хранение summaries (Pattern 4)
├── thread_parser.py          # Парсинг тредов (Pattern 6)
├── thread_store.py           # Хранение тредов (Pattern 6)
└── thread_summarization.py   # Суммаризация тредов (Pattern 6)

Qdrant Collections:
├── rag_embeddings           # Основные документы
├── document_summaries       # Pre-computed summaries (Pattern 4)
├── chat_messages           # Сообщения тредов (Pattern 6)
└── thread_summaries        # Summaries тредов (Pattern 6)
```

---

## Паттерн 1: Прямая суммаризация

### Описание

Базовый паттерн - прямая суммаризация документа по запросу с использованием Map-Reduce для больших документов.

### API

```bash
POST /summarize
{
  "doc_id": "document_123",
  "space_id": "demo",
  "focus": "Budget and timeline" # optional
}
```

### Алгоритм

```python
if document_tokens <= 8000:
    # Простая суммаризация одним вызовом LLM
    summary = call_llm(document_text)
else:
    # Map-Reduce для больших документов
    # MAP фаза: разбить на чанки и суммаризировать каждый
    chunk_summaries = []
    for chunk in split_document(6000 tokens):
        chunk_summary = call_llm(chunk)
        chunk_summaries.append(chunk_summary)
    
    # REDUCE фаза: объединить summaries
    final_summary = call_llm(combine(chunk_summaries))
```

### Особенности

- **Map-Reduce** автоматически для документов > 8K токенов
- **Focus parameter** для целевой суммаризации
- **Токен подсчёт** для определения стратегии
- **Error handling** с fallback

### Response

```json
{
  "doc_id": "document_123",
  "space_id": "demo",
  "summary": "This document discusses...",
  "chunks_processed": 25,
  "focus": "Budget and timeline",
  "cached": false
}
```

### Use Cases

- Получить краткое содержание документа
- Понять суть без чтения полностью
- Извлечь информацию по конкретному аспекту (focus)

### Преимущества

✅ Работает с документами любого размера  
✅ Сохраняет детали через Map-Reduce  
✅ Фокусированная суммаризация  
✅ Простой API

### Ограничения

⚠️ Медленно (5-20 секунд)  
⚠️ Повторные запросы генерируют заново  
⚠️ Нет кэширования

---

## Паттерн 2: Smart Context Compression

### Описание

Автоматическая суммаризация контекста в `/ask` когда найденные чанки превышают `context window` модели. Пороги адаптируются под каждую LLM.

### Конфигурация моделей

**Файл:** `config/llm_models.json`

```json
{
  "model_name": "llama3.1:8b",
  "context_window": 8192,
  "max_output_tokens": 512,
  "summarization_threshold": 3000,  # Порог авто-суммаризации
  "summarization_max_output": 1500  # Макс токенов в summary
}
```

**Формула порога:**
```python
summarization_threshold = effective_context_for_rag * 0.4
effective_context = context_window - max_output_tokens - 500 (overhead)
```

### Алгоритм в `/ask`

```python
# 1. Поиск и ranking
results = search(query, top_k=20)  # Находим релевантные чанки

# 2. Подсчёт токенов
context_tokens = count_tokens(results)

# 3. Получить конфиг модели
model_config = get_current_model_config()
threshold = model_config.summarization_threshold  # 3000 для llama3.1:8b

# 4. Решение
if context_tokens > threshold:  # 5000 > 3000
    # Суммаризировать контекст
    summary = summarize_chunks(results, query, max_tokens=1500)
    prompt = build_prompt_with_summary(summary, query)
else:
    # Обычный RAG
    prompt = build_prompt(results, query)

# 5. Генерация ответа
answer = call_llm(prompt)
```

### Примеры для разных моделей

| Модель | Context | Threshold | Поведение |
|--------|---------|-----------|-----------|
| **Llama 8B** | 8K | 3K | Часто суммаризирует |
| **Llama 70B FP8** | 16K | 6K | Средне |
| **Mixtral 8x7B** | 32K | 12K | Редко |
| **GPT-4 Turbo** | 128K | 50K | Почти никогда |

### Response `/ask`

```json
{
  "answer": "Based on the documents...",
  "sources": [...],
  "summarized": true,        # Была ли суммаризация
  "context_tokens": 5000,    # Исходный размер
  "model": "llama3.1:8b"
}
```

### Endpoint для конфигурации

```bash
GET /model-config

# Response:
{
  "model_name": "llama3.1:8b",
  "context_window": 8192,
  "summarization_threshold": 3000,
  "effective_context_for_rag": 7180,
  "tokens_per_second": 50
}
```

### Use Cases

- RAG с большим `top_k` (20-50 документов)
- Модели с малым context window
- Экономия токенов
- Оптимизация latency

### Преимущества

✅ Автоматическая адаптация под модель  
✅ Прозрачно для пользователя  
✅ Экономит токены (до 75%)  
✅ Работает out-of-the-box

### Ограничения

⚠️ Может потерять детали при суммаризации  
⚠️ Добавляет latency (если срабатывает)

---

## Паттерн 3: Режимы работы

### Описание

Явный контроль суммаризации через параметр `mode` в `/ask`. Пользователь или frontend выбирает поведение.

### Режимы

#### 1. `mode: "auto"` (по умолчанию)
Умное решение на основе порога модели (как в Паттерне 2).

```bash
POST /ask
{
  "q": "What are the project deadlines?",
  "space_id": "demo",
  "mode": "auto"
}
```

#### 2. `mode: "normal"`
Обычный RAG без суммаризации, независимо от размера контекста.

```bash
POST /ask
{
  "q": "List all deadlines",
  "mode": "normal",
  "top_k": 20
}
# → Отдаст все 20 чанков в LLM
```

#### 3. `mode: "summarize"`
Принудительная суммаризация, даже если контекст малый.

```bash
POST /ask
{
  "q": "Give me a brief overview",
  "mode": "summarize"
}
# → Суммаризирует даже 2-3 чанка
```

#### 4. `mode: "detailed"`
Максимально детальный ответ без суммаризации.

```bash
POST /ask
{
  "q": "List ALL project details with dates",
  "mode": "detailed",
  "top_k": 50
}
# → Никогда не суммаризирует
```

### Response

```json
{
  "answer": "...",
  "mode": "summarize",      # Использованный режим
  "summarized": true,       # Была ли суммаризация
  "context_tokens": 2000
}
```

### Матрица решений

```
Вопрос                          → Рекомендуемый режим
────────────────────────────────────────────────────
"Дай краткий обзор..."          → summarize
"Перечисли ВСЕ..."              → detailed
"Что такое X?"                  → normal
Не уверен                       → auto
```

### Frontend Integration

```typescript
// React компонент
const [mode, setMode] = useState<'auto' | 'normal' | 'summarize' | 'detailed'>('auto');

<select value={mode} onChange={e => setMode(e.target.value)}>
  <option value="auto">🤖 Smart</option>
  <option value="summarize">📄 Brief</option>
  <option value="detailed">📋 Detailed</option>
</select>

// API call
const response = await fetch('/ask', {
  body: JSON.stringify({
    q: question,
    mode: mode
  })
});

// Показать индикатор
{response.summarized && (
  <Badge>Summarized from {response.context_tokens} tokens</Badge>
)}
```

### Use Cases

- **Dashboard**: `mode: "summarize"` для быстрых карточек
- **Analytics**: `mode: "detailed"` для отчётов
- **Chat**: `mode: "auto"` для обычных вопросов
- **Search results**: `mode: "normal"` для точных цитат

### Преимущества

✅ Явный контроль для пользователя  
✅ Разные use cases  
✅ Graceful fallback на `auto`  
✅ Frontend-friendly

---

## Паттерн 4: Предвычисленные summaries

### Описание

Pre-compute summaries при индексации документа и сохранение в отдельной Qdrant коллекции. Instant retrieval вместо генерации.

### Архитектура

**Две коллекции:**

```
rag_embeddings (основная):
├── chunk 0: {text, doc_id, has_summary: true, summary_id: "uuid"}
├── chunk 1: {text, doc_id, has_summary: true}
└── ...

document_summaries (новая):
└── {
      doc_id: "doc_123",
      summary: "Full summary text...",
      summary_tokens: 150,
      generated_at: "2025-01-10",
      model: "llama3.1:8b"
    }
```

### API

#### 1. Индексация с summary

```bash
POST /ingest?generate_summary=true
  -F file=@document.pdf
  -F space_id=demo

# Response (через 3 секунды):
{
  "doc_id": "doc_123",
  "chunks_indexed": 25,
  "summary_pending": true  # В фоне!
}
```

**Flow:**
```
1. Парсинг и chunking (3s)
2. Индексация в rag_embeddings
3. Возврат response
4. Background task:
   - Генерация summary (15s)
   - Сохранение в document_summaries
   - Обновление has_summary=true
```

#### 2. Получение summary

```bash
POST /summarize
{
  "doc_id": "doc_123",
  "space_id": "demo"
}

# Response (0.1 секунда!):
{
  "summary": "...",
  "cached": true,         # Из кэша!
  "generated_at": "..."
}
```

#### 3. Проверка статуса

```bash
GET /documents/doc_123/summary-status?space_id=demo

{
  "has_summary": true,
  "summary_preview": "This document...",
  "summary_tokens": 150,
  "generated_at": "2025-01-10"
}
```

#### 4. Bulk операции

```bash
# Суммаризировать все документы без summaries
POST /bulk-summarize?space_id=demo&limit=100

{
  "documents_to_process": 15,
  "doc_ids": ["doc_1", "doc_2", ...],
  "status": "scheduled"
}
```

#### 5. Регенерация

```bash
# После смены модели LLM
POST /documents/doc_123/regenerate-summary?space_id=demo

{
  "status": "pending",
  "message": "Summary regeneration scheduled"
}
```

#### 6. Статистика

```bash
GET /summary-stats?space_id=demo

{
  "total_summaries": 45,
  "total_tokens": 6750,
  "average_tokens": 150,
  "by_space": {...},
  "by_doc_type": {...}
}
```

### Performance

| Operation | Без кэша | С кэшом | Улучшение |
|-----------|----------|---------|-----------|
| Первый `/summarize` | 15s | 15s | - |
| Повторный | 15s | **0.1s** | **150x** |
| Dashboard (10 docs) | 150s | **1s** | **150x** |
| Время `/ingest` | 3s | **3s** | Без влияния |

### Use Cases

#### 1. Document Library
```typescript
// Instant previews
const docs = await fetchDocuments();

for (const doc of docs) {
  const status = await fetch(`/documents/${doc.id}/summary-status`);
  if (status.has_summary) {
    showPreview(status.summary_preview);
  }
}
// ✅ Мгновенные превью
```

#### 2. Dashboard Cards
```typescript
// Load summaries for all projects
const summaries = await Promise.all(
  projectIds.map(id => fetch('/summarize', {body: {doc_id: id}}))
);
// ✅ Все из кэша, instant load
```

#### 3. Batch Upload
```typescript
// Upload many documents
for (const file of files) {
  await uploadFile(file, {generate_summary: true});
}
// ✅ Summaries генерируются в фоне
```

### Преимущества

✅ 150x быстрее повторные запросы  
✅ Не блокирует индексацию  
✅ Dashboard-friendly  
✅ Легко обновлять при смене модели

### Ограничения

⚠️ Дополнительное хранилище (summaries collection)  
⚠️ Немного сложнее архитектура

---

## Паттерн 5: Потоковая суммаризация

### Описание

Progressive streaming с Server-Sent Events (SSE). Пользователь видит прогресс, partial results и ETA вместо слепого ожидания.

### API

```bash
POST /summarize-stream
{
  "doc_id": "large_document",
  "space_id": "demo"
}

# Server-Sent Events (SSE):
data: {"type":"start","total_tokens":15000,"strategy":"map_reduce","progress":0}

data: {"type":"processing","progress":5,"eta_seconds":45}

data: {"type":"progress","stage":"map","current":1,"total":3,"progress":30,"eta_seconds":30}

data: {"type":"partial_summary","chunk":1,"summary":"Section 1 discusses..."}

data: {"type":"progress","stage":"reduce","progress":75}

data: {"type":"summary","text":"Final summary...","progress":100}

data: {"type":"complete","total_time":42.5}
```

### Event Types

| Type | Описание | Fields |
|------|----------|--------|
| `start` | Начало процесса | `total_tokens`, `strategy`, `map_chunks` |
| `processing` | Обработка | `message`, `progress`, `eta_seconds` |
| `progress` | Map/Reduce прогресс | `stage`, `current`, `total`, `eta_seconds` |
| `partial_summary` | Промежуточный результат | `chunk`, `summary`, `tokens` |
| `summary` | Финальный текст | `text`, `tokens`, `processing_time` |
| `complete` | Завершение | `total_time`, `tokens_processed` |
| `cached` | Из кэша | `summary`, `progress`: 100 |
| `error` | Ошибка | `message` |

### ETA Calculation

```python
model_config = get_current_model_config()
tokens_per_second = model_config.tokens_per_second  # 50 для llama3.1:8b

remaining_tokens = total_tokens - processed_tokens
eta_seconds = remaining_tokens / tokens_per_second

# Для Map-Reduce добавляем overhead
if strategy == "map_reduce":
    eta_seconds *= 1.5  # +50% на объединение
```

### Frontend Integration

```typescript
async function streamingSummarize(docId: string) {
  const response = await fetch('/summarize-stream', {
    method: 'POST',
    body: JSON.stringify({doc_id: docId, space_id: 'demo'})
  });
  
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  
  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    const events = chunk.split('\n')
      .filter(line => line.startsWith('data: '))
      .map(line => JSON.parse(line.substring(6)));
    
    for (const event of events) {
      switch (event.type) {
        case 'progress':
          updateProgress(event.progress, event.eta_seconds);
          break;
        case 'partial_summary':
          addPartialResult(event.chunk, event.summary);
          break;
        case 'summary':
          showFinalSummary(event.text);
          break;
      }
    }
  }
}
```

### Visual Demo

**Файл:** `static/streaming_demo.html`

Beautiful responsive UI:
- Progress bar с процентами
- Status messages с ETA
- Spinner animation
- Partial results display
- Cancel button
- Error handling

**Открыть:**
```bash
open http://localhost:8000/static/streaming_demo.html
```

### Long Polling Fallback

Для браузеров без SSE:

```bash
POST /summarize-poll
{
  "doc_id": "doc_123",
  "space_id": "demo"
}

# Response:
{
  "task_id": "task_abc",
  "status": "pending",
  "recommendation": "Use /summarize-stream for real-time progress"
}
```

### Use Cases

- **Большие документы** (100+ страниц, 15K+ токенов)
- **Interactive dashboards** с visual feedback
- **User-facing applications** где UX важен
- **Multi-document summaries** с long processing time

### Comparison

| Feature | `/summarize` | `/summarize-stream` |
|---------|--------------|---------------------|
| **Feedback** | ❌ Нет | ✅ Real-time |
| **Progress** | ❌ Нет | ✅ 0-100% |
| **ETA** | ❌ Нет | ✅ Да |
| **Partial results** | ❌ Нет | ✅ Да |
| **Cancellable** | ❌ Нет | ✅ Да |
| **Wait feeling** | 😴 Долго | 👀 Видит прогресс |

### Преимущества

✅ Мгновенная обратная связь  
✅ User engagement  
✅ Можно отменить  
✅ Видны промежуточные результаты  
✅ ETA visibility

### Ограничения

⚠️ Сложнее frontend integration  
⚠️ Требует SSE support в браузере

---

## Паттерн 6: Суммаризация тредов

### Описание

Structured summarization conversation threads (email, chat, messengers) с автоматическим извлечением action items, decisions и topics.

### Два use case

#### 1. User Chat (Real-time)
Сохранение сообщений пользовательского чата и суммаризация по требованию.

#### 2. File Upload
Парсинг и индексация email/chat файлов с автоматической суммаризацией.

### Архитектура

**Три новые коллекции:**

```
chat_messages:
├── {thread_id, sender, text, timestamp, chat_type, recipients}
└── Индексы: thread_id, space_id, sender

thread_summaries:
├── {thread_id, summary, action_items[], decisions[], topics[]}
├── {participants[], message_count, start_date, end_date}
└── Индекс: thread_id, space_id
```

### Поддерживаемые форматы

#### Email
```
From: Alice <alice@example.com>
Date: Mon, 10 Jan 2025 10:00:00
To: Bob <bob@example.com>
Subject: Project Discussion

Message body...
```

#### Telegram
```
[10.01.2025, 10:00] Alice: Message text
[10.01.2025, 10:05] Bob: Reply text
```

#### WhatsApp
```
10/01/2025, 10:00 - Alice: Message text
10/01/2025, 10:05 - Bob: Reply text
```

### API: User Chat

#### Сохранить сообщение

```bash
POST /chat/message
{
  "thread_id": "project_alpha",
  "space_id": "demo",
  "sender": "Alice",
  "text": "Bob, can you prepare the budget by Friday?",
  "recipients": ["Bob"],
  "chat_type": "user_chat"
}

# Response:
{
  "message_id": "msg_uuid",
  "thread_id": "project_alpha",
  "status": "saved"
}
```

#### Получить сообщения

```bash
GET /chat/thread/project_alpha/messages?space_id=demo&limit=100

{
  "message_count": 15,
  "messages": [
    {
      "sender": "Alice",
      "text": "...",
      "timestamp": "2025-01-10T10:00:00"
    },
    ...
  ]
}
```

#### Суммаризировать тред

```bash
POST /thread/summarize
{
  "thread_id": "project_alpha",
  "space_id": "demo",
  "extract_action_items": true,
  "extract_decisions": true,
  "extract_topics": true
}

# Response:
{
  "thread_id": "project_alpha",
  "summary": "Team discussed budget preparation. Alice requested completion by Friday. Bob committed to Wednesday delivery.",
  
  "participants": ["Alice", "Bob"],
  "message_count": 15,
  "start_date": "2025-01-10",
  "end_date": "2025-01-12",
  
  "action_items": [
    {
      "task": "Prepare budget",
      "owner": "Bob",
      "deadline": "Wednesday",
      "priority": null
    }
  ],
  
  "decisions": [
    "Budget deadline set to Friday",
    "Bob responsible for preparation"
  ],
  
  "topics": [
    "Budget Planning",
    "Timeline",
    "Responsibilities"
  ]
}
```

#### Получить сохраненный summary

```bash
GET /thread/project_alpha/summary?space_id=demo

# Instant retrieval из thread_summaries collection
```

### API: File Upload

```bash
POST /ingest-thread
  -F file=@email_thread.txt
  -F space_id=demo
  -F thread_type=email
  -F auto_summarize=true

# Response:
{
  "thread_id": "email_thread_abc123",
  "messages": 8,
  "participants": ["Alice", "Bob", "Charlie"],
  "start_date": "2025-01-10",
  "end_date": "2025-01-15",
  "summary_pending": true  # В фоне
}
```

### Action Items

**Что это:**
Автоматическое извлечение задач, TODO и assignments из разговора.

**Примеры извлечения:**

```
Фраза в чате → Action Item

"Bob, prepare report by Monday"
→ {task: "Prepare report", owner: "Bob", deadline: "Monday"}

"Alice will review the proposal"
→ {task: "Review proposal", owner: "Alice", deadline: null}

"We need to schedule a meeting (high priority)"
→ {task: "Schedule meeting", owner: null, deadline: null, priority: "high"}

"Charlie, finish design by EOW"
→ {task: "Finish design", owner: "Charlie", deadline: "end of week"}
```

**Use Cases:**
- Dashboard с задачами команды
- Автоматические напоминания
- Интеграция с Jira/Asana
- Task tracking
- Deadline monitoring

### Список тредов

```bash
GET /threads?space_id=demo&chat_type=email_thread&limit=50

{
  "thread_count": 12,
  "threads": [
    {
      "thread_id": "email_001",
      "chat_type": "email_thread",
      "participants": ["Alice", "Bob"],
      "message_count": 8,
      "start_date": "2025-01-10",
      "summary_preview": "Discussion about...",
      "has_action_items": true
    },
    ...
  ]
}
```

### Удаление треда

```bash
DELETE /thread/project_alpha?space_id=demo

# Удаляет:
# - Все сообщения из chat_messages
# - Summary из thread_summaries
```

### Use Cases

#### 1. Team Chat Application
```typescript
// Real-time сохранение
socket.on('message', async (msg) => {
  await saveMessage(conversationId, msg.user, msg.text);
});

// End of day summary
const summary = await summarizeThread(conversationId);
showTeamSummary(summary);
showActionItems(summary.action_items);
```

#### 2. Email Archive
```bash
# Bulk индексация email тредов
for file in emails/*.txt; do
  curl -F "file=@$file" -F "thread_type=email" /ingest-thread
done

# Поиск через RAG по всем email
curl '/ask' -d '{"q":"What was decided about the budget?"}'
```

#### 3. Action Items Dashboard
```typescript
const threads = await getThreads();
const allActions = threads
  .filter(t => t.has_action_items)
  .flatMap(t => t.action_items);

const byOwner = groupBy(allActions, 'owner');
const byDeadline = sortBy(allActions, 'deadline');

<ActionItemsBoard 
  items={allActions}
  groupBy="owner"
  showDeadlines={true}
/>
```

#### 4. Meeting Notes Alternative
```typescript
// Вместо записи meeting notes
// 1. Чат во время meeting
chatDuringMeeting(meetingId);

// 2. Auto-generate summary
const summary = await summarizeThread(meetingId);

// 3. Распределить action items
distributeActionItems(summary.action_items);

// 4. Сохранить decisions
recordDecisions(summary.decisions);
```

### Преимущества

✅ Структурированная информация  
✅ Автоматическая экстракция action items  
✅ Сохранение истории в Qdrant  
✅ Поддержка multiple форматов  
✅ Real-time и file upload  
✅ Searchable через RAG

### Ограничения

⚠️ Качество экстракции зависит от LLM  
⚠️ Action items могут требовать review

---

## Архитектура системы

### Модули

```
backend/services/
├── summarization.py              # Core: Map-Reduce, streaming
│   ├── summarize_text()         # Простая суммаризация
│   ├── summarize_long_text()    # Map-Reduce
│   ├── summarize_document_by_id() # По doc_id
│   ├── summarize_chunks()       # Из search results
│   └── summarize_document_streaming() # SSE streaming
│
├── llm_config.py                # Model configurations
│   ├── LLMModelConfig          # Dataclass
│   ├── LLMModelRegistry        # Registry
│   └── get_current_model_config() # Active model
│
├── summary_store.py             # Pre-computed summaries
│   ├── save_document_summary()
│   ├── get_document_summary()
│   └── Collection: document_summaries
│
├── thread_parser.py             # Thread parsing
│   ├── parse_email_thread()
│   ├── parse_telegram_chat()
│   └── parse_whatsapp_chat()
│
├── thread_store.py              # Thread storage
│   ├── save_chat_message()
│   ├── get_thread_messages()
│   ├── save_thread_summary()
│   └── Collections: chat_messages, thread_summaries
│
└── thread_summarization.py     # Thread summarization
    ├── summarize_thread()
    └── Extract: action_items, decisions, topics
```

### Qdrant Collections

```
1. rag_embeddings (main)
   - Document chunks + embeddings
   - Payload: has_summary flag

2. document_summaries (Pattern 4)
   - Pre-computed document summaries
   - Fast retrieval

3. chat_messages (Pattern 6)
   - Individual messages
   - thread_id grouping

4. thread_summaries (Pattern 6)
   - Structured thread summaries
   - action_items, decisions, topics
```

### API Endpoints

```
Document Summarization:
├── POST /summarize              # Pattern 1: Direct
├── POST /summarize-stream       # Pattern 5: Streaming (SSE)
├── POST /summarize-poll         # Pattern 5: Long polling fallback
├── GET  /documents/{id}/summary-status  # Pattern 4: Check status
├── POST /documents/{id}/regenerate-summary  # Pattern 4: Regenerate
├── POST /bulk-summarize         # Pattern 4: Bulk operation
├── GET  /summary-stats          # Pattern 4: Statistics
└── DELETE /documents/{id}/summary  # Pattern 4: Delete

Context Compression (Pattern 2):
└── Integrated in POST /ask      # Smart auto-summarization

Mode Control (Pattern 3):
└── POST /ask?mode=auto|normal|summarize|detailed

Model Configuration (Pattern 2):
└── GET /model-config            # Current model settings

Thread Operations (Pattern 6):
├── POST /chat/message           # Save message
├── GET  /chat/thread/{id}/messages  # Get messages
├── POST /thread/summarize       # Summarize thread
├── GET  /thread/{id}/summary    # Get summary
├── POST /ingest-thread          # Upload thread file
├── GET  /threads                # List threads
└── DELETE /thread/{id}          # Delete thread
```

### Configuration Files

```
config/
└── llm_models.json              # Model configurations
    ├── Ollama models: llama3.1:8b, mistral:7b, qwen2.5:7b
    ├── vLLM models: Llama-8B, Llama-70B-FP8, Mixtral
    └── Cloud models: GPT-4, GPT-4 Turbo, Claude-3

docs/threads/
└── README.md                    # Thread file formats guide
```

---

## Интеграция и использование

### Quick Start

#### 1. Простая суммаризация

```bash
# Upload document
curl -F "file=@doc.pdf" -F "space_id=demo" /ingest

# Summarize
curl -X POST /summarize -d '{"doc_id":"doc_123","space_id":"demo"}'
```

#### 2. С кэшированием

```bash
# Upload с auto-summary
curl -F "file=@doc.pdf" -F "generate_summary=true" /ingest

# Instant retrieval (0.1s)
curl -X POST /summarize -d '{"doc_id":"doc_123","space_id":"demo"}'
# → cached: true
```

#### 3. Streaming для больших документов

```bash
curl -X POST /summarize-stream \
  -d '{"doc_id":"large_doc","space_id":"demo"}' \
  --no-buffer

# Real-time progress + ETA
```

#### 4. Smart RAG с контекст compression

```bash
# Автоматически суммаризирует если нужно
curl -X POST /ask \
  -d '{
    "q": "What are all the project deadlines?",
    "space_id": "demo",
    "top_k": 30
  }'

# Response: summarized: true/false
```

#### 5. Режимы работы

```bash
# Brief overview
curl -X POST /ask -d '{"q":"overview","mode":"summarize"}'

# Full details
curl -X POST /ask -d '{"q":"all details","mode":"detailed","top_k":50}'
```

#### 6. Thread summarization

```bash
# Save chat messages
curl -X POST /chat/message \
  -d '{"thread_id":"chat1","sender":"Alice","text":"..."}'

# Summarize with action items
curl -X POST /thread/summarize \
  -d '{"thread_id":"chat1","extract_action_items":true}'
```

### Production Recommendations

#### 1. Выбор паттернов

```
Use Case                          → Pattern
────────────────────────────────────────────
One-time doc summary              → Pattern 1
RAG with large top_k              → Pattern 2
User control needed               → Pattern 3
Document library/dashboard        → Pattern 4
Large docs, UX important          → Pattern 5
Chat/email processing             → Pattern 6
```

#### 2. Конфигурация

```bash
# .env
LLM_MODEL=llama3.1:8b
LLM_MODE=ollama

# Модель определяет пороги автоматически
# Смотри: config/llm_models.json
```

#### 3. Мониторинг

```bash
# Check summaries stats
curl /summary-stats?space_id=demo

# Model config
curl /model-config

# Thread stats
curl /threads?space_id=demo
```

#### 4. Performance Tuning

```yaml
# Для быстрой генерации: small model
LLM_MODEL: llama3.1:8b
tokens_per_second: 250 (vLLM)

# Для качества: large model
LLM_MODEL: llama3.1:70b
context_window: 16K

# Для очень больших документов
LLM_MODEL: mistralai/Mixtral-8x7B-Instruct-v0.1
context_window: 32K
```

### Комбинирование паттернов

#### Example 1: Document Library

```typescript
// Pattern 4: Pre-compute summaries при upload
await uploadDocuments(files, {generate_summary: true});

// Pattern 4: Instant display
const docs = await getDocuments();
for (const doc of docs) {
  const summary = await getSummary(doc.id);  // 0.1s, cached!
  showCard(doc, summary.summary_preview);
}
```

#### Example 2: Interactive Dashboard

```typescript
// Pattern 3: User control
const mode = userPreference;  // "summarize" for dashboard

// Pattern 2: Auto-optimization
const response = await ask(query, {
  mode: mode,
  top_k: 30
});

// Pattern 5: Streaming для detail view
if (needsDetail) {
  streamingSummarize(docId, showProgress);
}
```

#### Example 3: Team Collaboration

```typescript
// Pattern 6: Save chat messages
socket.on('message', msg => saveMessage(threadId, msg));

// Pattern 6: Daily summary
scheduleDaily(async () => {
  const summary = await summarizeThread(threadId);
  sendEmail(team, summary);
  
  // Extract action items
  createTasks(summary.action_items);
});

// Pattern 4: Cache summaries
await Promise.all(
  allThreads.map(t => summarizeThread(t.id))
);
```

---

## Заключение

### Что мы получили

**6 интегрированных паттернов:**

1. ✅ **Прямая суммаризация** - базовый функционал
2. ✅ **Smart Compression** - автоматическая оптимизация
3. ✅ **Режимы работы** - явный контроль
4. ✅ **Pre-computed** - 150x быстрее
5. ✅ **Streaming** - UX для больших документов
6. ✅ **Треды** - structured с action items

### Покрываемые сценарии

- ✅ Малые документы (< 8K токенов)
- ✅ Средние документы (8-32K токенов)
- ✅ Большие документы (32K+ токенов)
- ✅ RAG с множеством результатов
- ✅ Interactive applications
- ✅ Document libraries
- ✅ Dashboards
- ✅ Email/chat processing
- ✅ Team collaboration
- ✅ Action item tracking

### Архитектурные преимущества

- **Модульность**: каждый паттерн независим
- **Масштабируемость**: background tasks, streaming
- **Гибкость**: multiple режимы и опции
- **Performance**: кэширование, async
- **UX**: streaming, progress, ETA
- **Интеграция**: совместимость с существующим RAG

### Next Steps

**Возможные расширения:**

1. **Batch Processing**
   - Массовая обработка документов
   - Scheduled summaries

2. **Multi-language Support**
   - Суммаризация на разных языках
   - Translation + summarization

3. **Custom Templates**
   - Пользовательские промпты
   - Industry-specific summaries

4. **Analytics**
   - Tracking usage
   - Quality metrics
   - Cost optimization

5. **Notifications**
   - Action item reminders
   - Deadline alerts
   - Summary digests

### Документация

- [SUMMARIZATION_QUICKSTART.md](../SUMMARIZATION_QUICKSTART.md)
- [ASK_MODES_GUIDE.md](ASK_MODES_GUIDE.md)
- [SUMMARY_STORAGE_GUIDE.md](SUMMARY_STORAGE_GUIDE.md)
- [STREAMING_QUICKSTART.md](../STREAMING_QUICKSTART.md)
- [THREADS_QUICKSTART.md](../THREADS_QUICKSTART.md)
- [LLM_MODEL_CONFIGURATION.md](LLM_MODEL_CONFIGURATION.md)

---

**🎉 СИСТЕМА ГОТОВА К PRODUCTION ИСПОЛЬЗОВАНИЮ! 🎉**

