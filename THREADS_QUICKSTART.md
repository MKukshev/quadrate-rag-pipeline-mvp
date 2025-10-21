# Quick Start: Thread Summarization (Pattern 6)

## 🚀 TL;DR

Structured summarization of conversation threads (email, chat, messengers) with automatic extraction of action items, decisions, and topics.

---

## 📋 Key Features

1. **Two use cases:**
   - Parse & index thread files (email, Telegram, WhatsApp)
   - Store & summarize user chat messages in real-time

2. **Structured extraction:**
   - Summary of conversation
   - Action items (tasks, TODO, assignments)
   - Decisions made
   - Discussed topics
   - Participants timeline

3. **Separate storage:**
   - `chat_messages` collection - individual messages
   - `thread_summaries` collection - structured summaries

---

## 💻 Quick Examples

### 1. User Chat (Real-time)

```bash
# Save messages to a thread
curl -X POST http://localhost:8000/chat/message \
  -d '{
    "thread_id": "project_alpha_chat",
    "space_id": "demo",
    "sender": "Alice",
    "text": "We need to finalize the budget by Friday",
    "recipients": ["Bob", "Charlie"],
    "chat_type": "user_chat"
  }'

# Add more messages...
curl -X POST http://localhost:8000/chat/message \
  -d '{
    "thread_id": "project_alpha_chat",
    "space_id": "demo",
    "sender": "Bob",
    "text": "I can prepare the draft by Wednesday"
  }'

# Summarize the thread
curl -X POST http://localhost:8000/thread/summarize \
  -d '{
    "thread_id": "project_alpha_chat",
    "space_id": "demo",
    "extract_action_items": true,
    "extract_decisions": true
  }' | jq
```

**Response:**
```json
{
  "thread_id": "project_alpha_chat",
  "summary": "Team discussed budget finalization timeline. Bob committed to preparing draft by Wednesday for Friday deadline.",
  "participants": ["Alice", "Bob"],
  "action_items": [
    {
      "task": "Prepare budget draft",
      "owner": "Bob",
      "deadline": "Wednesday"
    }
  ],
  "decisions": [
    "Budget finalization deadline set to Friday"
  ],
  "topics": ["Budget Planning", "Timeline"]
}
```

---

### 2. Email Thread File

```bash
# Upload email thread
curl -X POST http://localhost:8000/ingest-thread \
  -F "file=@docs/email_correspondence/email_thread_001_project_discussion.txt" \
  -F "space_id=demo" \
  -F "thread_type=email" \
  -F "auto_summarize=true"

# Response
{
  "thread_id": "email_thread_001_abc123",
  "messages": 8,
  "participants": ["Alice", "Bob", "Charlie"],
  "start_date": "2025-01-10",
  "end_date": "2025-01-15",
  "summary_pending": true
}

# Wait ~10 seconds, then get summary
curl "http://localhost:8000/thread/email_thread_001_abc123/summary?space_id=demo" | jq
```

---

### 3. Telegram Chat

```bash
curl -X POST http://localhost:8000/ingest-thread \
  -F "file=@docs/messenger_correspondence/telegram_chat_001_team_discussion.txt" \
  -F "space_id=demo" \
  -F "thread_type=telegram"
```

---

## 🏗 Architecture

### Collections

```
Qdrant:
├── chat_messages
│   └── Individual messages with thread_id
│       • sender, text, timestamp
│       • thread_id, space_id
│       • chat_type, metadata
│
└── thread_summaries
    └── Structured summaries
        • summary text
        • action_items []
        • decisions []
        • topics []
        • participants []
```

### Flow

```
User Chat:
  POST /chat/message → chat_messages collection
  POST /thread/summarize → Generate & save to thread_summaries

File Upload:
  POST /ingest-thread → Parse → chat_messages
                     → Background: summarize → thread_summaries
```

---

## 📊 Action Items Explained

**Action Items** - это задачи и TODO, извлеченные из разговора:

```json
{
  "task": "Prepare budget draft",
  "owner": "Bob",         // Кто ответственен
  "deadline": "Friday",   // Срок
  "priority": "high"      // Приоритет (если упомянут)
}
```

**Примеры из чата:**
- "Bob, can you prepare the report by Monday?" → Action item
- "Alice will review the proposal" → Action item  
- "We need to schedule a meeting" → Action item

**Use cases:**
- Dashboard с задачами команды
- Напоминания о дедлайнах
- Tracking выполнения
- Автоматическое создание задач в task tracker

---

## 📚 API Endpoints

### User Chat

```bash
# Save message
POST /chat/message
{
  "thread_id": "chat123",
  "space_id": "demo",
  "sender": "Alice",
  "text": "Message content"
}

# Get messages
GET /chat/thread/{thread_id}/messages?space_id=demo

# Summarize thread
POST /thread/summarize
{
  "thread_id": "chat123",
  "space_id": "demo",
  "extract_action_items": true
}

# Get saved summary
GET /thread/{thread_id}/summary?space_id=demo
```

### File Upload

```bash
# Upload thread file
POST /ingest-thread
  -F file=@thread.txt
  -F space_id=demo
  -F thread_type=email  # email|telegram|whatsapp
  -F auto_summarize=true

# List all threads
GET /threads?space_id=demo&chat_type=email_thread

# Delete thread
DELETE /thread/{thread_id}?space_id=demo
```

---

## 🎯 Use Cases

### 1. Team Chat
```typescript
// Save messages as users chat
socket.on('message', async (msg) => {
  await fetch('/chat/message', {
    body: JSON.stringify({
      thread_id: conversationId,
      sender: msg.user,
      text: msg.content
    })
  });
});

// End of day summary
const summary = await fetch('/thread/summarize', {
  body: JSON.stringify({thread_id: conversationId})
});

showDailySummary(summary.data);
```

### 2. Email Archive
```bash
# Index all email threads
for file in docs/email_correspondence/*.txt; do
  curl -X POST http://localhost:8000/ingest-thread \
    -F "file=@$file" \
    -F "space_id=company" \
    -F "thread_type=email" \
    -F "auto_summarize=true"
done

# Search across all summaries via RAG
```

### 3. Action Item Dashboard
```typescript
// Get all threads with action items
const threads = await fetch('/threads?space_id=team');

const allActionItems = threads
  .filter(t => t.has_action_items)
  .flatMap(t => t.action_items);

// Group by owner
const byOwner = groupBy(allActionItems, 'owner');

// Show dashboard
<ActionItemsList items={byOwner} />
```

---

## 🧪 Test

```bash
# Test with existing files
curl -X POST http://localhost:8000/ingest-thread \
  -F "file=@docs/email_correspondence/email_thread_001_project_discussion.txt" \
  -F "space_id=demo" \
  -F "thread_type=email" \
  -F "auto_summarize=true"

# Get thread ID from response
THREAD_ID="..."

# Wait for summary
sleep 10

# Get structured summary
curl "http://localhost:8000/thread/${THREAD_ID}/summary?space_id=demo" | jq
```

---

**Status:** ✅ Integrated and ready to use!

**Learn more:** Full documentation coming soon

