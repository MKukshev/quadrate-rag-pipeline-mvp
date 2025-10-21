# API Examples: Access Control Integration

## 🔐 Аутентификация

Все запросы требуют JWT токен в заголовке:

```bash
Authorization: Bearer <token>
```

### Формат токена (для примера)
```
user_alice|company_acme|admin
user_bob|company_acme|member
bot_research_01|company_acme|agent:research
```

---

## 📤 Загрузка документов с контролем доступа

### Пример 1: Приватный документ (только владелец)

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer user_alice|company_acme|admin" \
  -F "file=@confidential_report.pdf" \
  -F "space_id=company_acme" \
  -F "channel_id=channel_leadership" \
  -F "doc_type=technical_docs" \
  -F "visibility=private" \
  -F "agent_roles=" \
  -F "security_level=5" \
  -F "department=management"
```

**Response:**
```json
{
  "doc_id": "confidential_report_a1b2c3d4",
  "space_id": "company_acme",
  "channel_id": "channel_leadership",
  "doc_type": "technical_docs",
  "chunks_indexed": 42,
  "visibility": "private",
  "owner_id": "user_alice",
  "allowed_agent_roles": []
}
```

### Пример 2: Командный документ с доступом для ботов

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer user_bob|company_acme|member" \
  -F "file=@architecture_design.md" \
  -F "space_id=company_acme" \
  -F "channel_id=channel_engineering" \
  -F "doc_type=technical_docs" \
  -F "visibility=team" \
  -F "agent_roles=research,analytics" \
  -F "security_level=2" \
  -F "department=engineering"
```

### Пример 3: Публичный FAQ для support бота

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer user_alice|company_acme|admin" \
  -F "file=@faq.txt" \
  -F "space_id=company_acme" \
  -F "doc_type=protocols" \
  -F "visibility=public" \
  -F "agent_roles=support,research,analytics" \
  -F "security_level=0"
```

---

## 🔍 Поиск с контролем доступа

### Пример 4: Поиск от имени пользователя

```bash
curl -X GET "http://localhost:8000/search?q=архитектура%20микросервисов&space_id=company_acme&channel_id=channel_engineering&top_k=5" \
  -H "Authorization: Bearer user_bob|company_acme|member"
```

**Response:**
```json
{
  "query": "архитектура микросервисов",
  "space_id": "company_acme",
  "channel_id": "channel_engineering",
  "doc_types": ["technical_docs"],
  "results": [
    {
      "key": "architecture_design_a1b2:0",
      "score": 0.89,
      "payload": {
        "doc_id": "architecture_design_a1b2",
        "space_id": "company_acme",
        "channel_id": "channel_engineering",
        "doc_type": "technical_docs",
        "chunk_index": 0,
        "text": "Микросервисная архитектура состоит из...",
        "visibility": "team",
        "owner_id": "user_bob",
        "security_level": 2
      }
    }
  ],
  "access_context": {
    "user_id": "user_bob",
    "agent_id": null,
    "agent_role": null
  }
}
```

### Пример 5: Поиск от имени Research бота

```bash
curl -X GET "http://localhost:8000/search?q=технические%20требования&space_id=company_acme&top_k=3&agent_id=bot_research_01&agent_role=research" \
  -H "Authorization: Bearer bot_research_01|company_acme|agent"
```

**Бот видит только:**
- `technical_docs`
- `work_plans`
- `presentations`
- `protocols`
- `unstructured`

**Бот НЕ видит:**
- `email_correspondence`
- `messenger_correspondence`
- Документы с `visibility=private` (кроме явно разрешенных)

### Пример 6: Поиск от имени Support бота

```bash
curl -X GET "http://localhost:8000/search?q=как%20сбросить%20пароль&space_id=company_acme&agent_id=bot_support_01&agent_role=support" \
  -H "Authorization: Bearer bot_support_01|company_acme|agent"
```

**Support бот видит только:**
- `protocols`
- `technical_docs`
- `email_correspondence` (FAQ и инструкции)

### Пример 7: Поиск от имени Analytics бота (полный доступ)

```bash
curl -X GET "http://localhost:8000/search?q=статистика%20проектов&space_id=company_acme&agent_id=bot_analytics_01&agent_role=analytics" \
  -H "Authorization: Bearer bot_analytics_01|company_acme|agent"
```

**Analytics бот видит все документы** (кроме `visibility=private` без явного доступа)

---

## 💬 RAG (Ask) с контролем доступа

### Пример 8: Вопрос от пользователя

```bash
curl -X POST http://localhost:8000/ask \
  -H "Authorization: Bearer user_alice|company_acme|admin" \
  -H "Content-Type: application/json" \
  -d '{
    "q": "Какие дедлайны по проекту миграции?",
    "space_id": "company_acme",
    "channel_id": "channel_engineering",
    "top_k": 5,
    "doc_types": ["work_plans", "email_correspondence"]
  }'
```

**Response:**
```json
{
  "answer": "По проекту миграции установлены следующие дедлайны: 1) Завершение анализа - 15 ноября 2025, 2) Разработка плана - 30 ноября 2025, 3) Тестирование - 20 декабря 2025, 4) Production rollout - 10 января 2026.",
  "sources": [
    {
      "doc_id": "migration_plan_xyz",
      "chunk_index": 3,
      "doc_type": "work_plans",
      "visibility": "team",
      "owner_id": "user_alice"
    },
    {
      "doc_id": "email_thread_migration",
      "chunk_index": 12,
      "doc_type": "email_correspondence",
      "visibility": "channel",
      "owner_id": "user_bob"
    }
  ]
}
```

### Пример 9: Вопрос от Research бота

```bash
curl -X POST http://localhost:8000/ask \
  -H "Authorization: Bearer bot_research_01|company_acme|agent" \
  -H "Content-Type: application/json" \
  -d '{
    "q": "Опиши архитектуру системы аутентификации",
    "space_id": "company_acme",
    "agent_id": "bot_research_01",
    "agent_role": "research",
    "top_k": 5
  }'
```

---

## 📋 Управление доступом к документам

### Пример 10: Просмотр своих документов

```bash
curl -X GET "http://localhost:8000/my-documents?space_id=company_acme" \
  -H "Authorization: Bearer user_alice|company_acme|admin"
```

**Response:**
```json
{
  "documents": [
    {
      "doc_id": "confidential_report_a1b2c3d4",
      "doc_type": "technical_docs",
      "visibility": "private",
      "security_level": 5,
      "chunks": 42
    },
    {
      "doc_id": "faq_x7y8z9",
      "doc_type": "protocols",
      "visibility": "public",
      "security_level": 0,
      "chunks": 15
    }
  ]
}
```

### Пример 11: Изменение прав доступа к документу

```bash
# Пользователь Alice делится документом с Bob и research ботом
curl -X POST http://localhost:8000/document-access \
  -H "Authorization: Bearer user_alice|company_acme|admin" \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "confidential_report_a1b2c3d4",
    "visibility": "team",
    "access_list": ["user_bob", "user_charlie"],
    "agent_roles": ["research"]
  }'
```

**Response:**
```json
{
  "status": "ok",
  "doc_id": "confidential_report_a1b2c3d4"
}
```

### Пример 12: Попытка изменить чужой документ (ошибка)

```bash
curl -X POST http://localhost:8000/document-access \
  -H "Authorization: Bearer user_bob|company_acme|member" \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "confidential_report_a1b2c3d4",
    "visibility": "public"
  }'
```

**Response (403):**
```json
{
  "detail": "User user_bob cannot modify document confidential_report_a1b2c3d4"
}
```

---

## 🗑️ Удаление документов

### Пример 13: Удаление своего документа

```bash
curl -X DELETE http://localhost:8000/document/architecture_design_a1b2 \
  -H "Authorization: Bearer user_bob|company_acme|member"
```

**Response:**
```json
{
  "status": "deleted",
  "doc_id": "architecture_design_a1b2"
}
```

### Пример 14: Admin удаляет любой документ

```bash
curl -X DELETE http://localhost:8000/document/old_report_xyz \
  -H "Authorization: Bearer user_alice|company_acme|admin"
```

---

## 🤖 Сценарии использования ботов-агентов

### Сценарий 1: Research бот помогает команде

**Контекст:** В канале engineering команда обсуждает новую архитектуру

```bash
# 1. Пользователь задает вопрос в чате
User: "@research_bot как масштабировать нашу систему?"

# 2. Бот делает запрос к RAG с ограниченным доступом
curl -X POST http://localhost:8000/ask \
  -H "Authorization: Bearer bot_research_01|company_acme|agent" \
  -H "Content-Type: application/json" \
  -d '{
    "q": "как масштабировать систему",
    "space_id": "company_acme",
    "channel_id": "channel_engineering",
    "agent_id": "bot_research_01",
    "agent_role": "research",
    "top_k": 3
  }'

# 3. Бот получает ответ на основе technical_docs, work_plans
# 4. Бот отвечает в чате с ссылками на источники
```

### Сценарий 2: Support бот отвечает клиенту

```bash
# Клиент спрашивает в support канале
Customer: "Как восстановить доступ к аккаунту?"

# Support бот ищет в protocols и FAQs
curl -X POST http://localhost:8000/ask \
  -H "Authorization: Bearer bot_support_01|company_acme|agent" \
  -H "Content-Type: application/json" \
  -d '{
    "q": "как восстановить доступ к аккаунту",
    "space_id": "company_acme",
    "agent_id": "bot_support_01",
    "agent_role": "support",
    "doc_types": ["protocols"],
    "top_k": 2
  }'
```

### Сценарий 3: Analytics бот собирает статистику

```bash
# Ночной cron job для аналитики
curl -X GET "http://localhost:8000/search?q=метрики%20производительности&space_id=company_acme&agent_id=bot_analytics_01&agent_role=analytics&top_k=50" \
  -H "Authorization: Bearer bot_analytics_01|company_acme|agent"

# Analytics бот видит ВСЕ документы для полного анализа
```

### Сценарий 4: Admin бот для мониторинга

```bash
# Admin бот проверяет безопасность
curl -X POST http://localhost:8000/ask \
  -H "Authorization: Bearer bot_admin_01|company_acme|agent" \
  -H "Content-Type: application/json" \
  -d '{
    "q": "найди все упоминания уязвимостей",
    "space_id": "company_acme",
    "agent_id": "bot_admin_01",
    "agent_role": "admin",
    "top_k": 20
  }'

# Admin бот имеет доступ ко ВСЕМ документам, включая private
```

---

## 🔄 Workflow: Жизненный цикл документа

### Шаг 1: Создание приватного черновика

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer user_alice|company_acme|admin" \
  -F "file=@draft_proposal.md" \
  -F "space_id=company_acme" \
  -F "doc_type=work_plans" \
  -F "visibility=private" \
  -F "security_level=3"

# Видит только Alice
```

### Шаг 2: Поделиться с командой для ревью

```bash
curl -X POST http://localhost:8000/document-access \
  -H "Authorization: Bearer user_alice|company_acme|admin" \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "draft_proposal_xyz",
    "visibility": "team",
    "access_list": ["user_bob", "user_charlie"],
    "agent_roles": ["research"]
  }'

# Теперь видят: Alice, Bob, Charlie, Research бот
```

### Шаг 3: Публикация для всей компании

```bash
curl -X POST http://localhost:8000/document-access \
  -H "Authorization: Bearer user_alice|company_acme|admin" \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "draft_proposal_xyz",
    "visibility": "public",
    "security_level": 1,
    "agent_roles": ["research", "support", "analytics"]
  }'

# Теперь видят все в space_id=company_acme
```

### Шаг 4: Архивация или удаление

```bash
curl -X DELETE http://localhost:8000/document/draft_proposal_xyz \
  -H "Authorization: Bearer user_alice|company_acme|admin"
```

---

## 🎭 Матрица доступа по ролям

| Роль агента | Видит doc_types | Ограничения visibility |
|-------------|-----------------|------------------------|
| `research` | technical_docs, work_plans, presentations, protocols | team, channel, public |
| `support` | protocols, technical_docs, email (FAQ) | channel, public |
| `analytics` | ALL | team, channel, public |
| `summarizer` | email_correspondence, messenger_correspondence | team, channel, public |
| `admin` | ALL | ALL (включая private) |

| Роль пользователя | Может видеть | Может редактировать | Может удалять |
|-------------------|--------------|---------------------|---------------|
| `guest` | public | - | - |
| `member` | public, team, channel, own private | own | own |
| `admin` | ALL | ALL | ALL |
| `owner` | ALL | ALL | ALL |

---

## ⚠️ Примеры ошибок доступа

### 403 Forbidden: Нет доступа к space

```bash
curl -X GET "http://localhost:8000/search?q=test&space_id=other_company" \
  -H "Authorization: Bearer user_alice|company_acme|admin"
```

**Response:**
```json
{
  "detail": "Access denied to this space"
}
```

### 403 Forbidden: Бот пытается получить приватный документ

```bash
# Research бот пытается найти private документ без явного доступа
curl -X GET "http://localhost:8000/search?q=confidential&space_id=company_acme&agent_id=bot_research_01&agent_role=research"

# Результаты будут отфильтрованы - private документы не вернутся
```

### 401 Unauthorized: Невалидный токен

```bash
curl -X GET "http://localhost:8000/search?q=test" \
  -H "Authorization: Bearer invalid_token"
```

**Response:**
```json
{
  "detail": "Invalid authentication token"
}
```

---

## 🧪 Тестирование ACL

### Тест 1: Изоляция spaces

```bash
# User A в space_1
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer user_a|space_1|admin" \
  -F "file=@doc1.txt" -F "space_id=space_1"

# User B в space_2
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer user_b|space_2|admin" \
  -F "file=@doc2.txt" -F "space_id=space_2"

# User A НЕ видит документы space_2
curl -X GET "http://localhost:8000/search?q=test&space_id=space_2" \
  -H "Authorization: Bearer user_a|space_1|admin"
# -> 403 Forbidden
```

### Тест 2: Visibility levels

```bash
# Private document
curl ... -F "visibility=private" -F "space_id=test_space"
# -> Видит только owner

# Team document
curl ... -F "visibility=team" -F "space_id=test_space"
# -> Видят все member в space

# Channel document
curl ... -F "visibility=channel" -F "channel_id=test_channel"
# -> Видят только участники channel

# Public document
curl ... -F "visibility=public" -F "space_id=test_space"
# -> Видят все в space
```

### Тест 3: Agent role restrictions

```python
# Research бот НЕ должен видеть email_correspondence
results = search(agent_role="research", doc_types=["email_correspondence"])
assert len(results) == 0

# Support бот НЕ должен видеть work_plans
results = search(agent_role="support", doc_types=["work_plans"])
assert len(results) == 0

# Admin бот видит все
results = search(agent_role="admin", doc_types=["email_correspondence"])
assert len(results) > 0
```

---

## 📚 Интеграция с фронтендом

### JavaScript/TypeScript пример

```typescript
// auth.ts
export const getAuthToken = () => {
  return localStorage.getItem('jwt_token');
};

// api.ts
export async function searchDocuments(query: string, options: {
  spaceId: string;
  channelId?: string;
  docTypes?: string[];
  topK?: number;
}) {
  const response = await fetch(
    `/search?q=${encodeURIComponent(query)}&space_id=${options.spaceId}` +
    `&top_k=${options.topK || 5}` +
    (options.channelId ? `&channel_id=${options.channelId}` : '') +
    (options.docTypes?.map(t => `&doc_types=${t}`).join('') || ''),
    {
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`
      }
    }
  );
  
  if (!response.ok) {
    if (response.status === 403) {
      throw new Error('Access denied');
    }
    throw new Error('Search failed');
  }
  
  return response.json();
}

// Использование
const results = await searchDocuments('архитектура системы', {
  spaceId: 'company_acme',
  channelId: 'channel_engineering',
  docTypes: ['technical_docs'],
  topK: 5
});
```

---

## 🔗 Полезные ссылки

- [Полная документация по архитектуре](./ACCESS_CONTROL_ARCHITECTURE.md)
- [Swagger UI](http://localhost:8000/docs)
- [Health Check](http://localhost:8000/health)

