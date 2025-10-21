# Суммаризация в AnythingLLM - Как и зачем используется

## 🎯 Основной use case

**Проблема:** Документ слишком большой, не влезает в контекст LLM  
**Решение:** Map-Reduce суммаризация через LangChain

---

## 🔍 Как работает суммаризация

### Алгоритм Map-Reduce

```javascript
// server/utils/agents/aibitat/utils/summarize.js

async function summarizeContent({ provider, model, content }) {
  // 1. Разбить на чанки (10K токенов каждый)
  const textSplitter = new RecursiveCharacterTextSplitter({
    chunkSize: 10000,
    chunkOverlap: 500,
  });
  const docs = await textSplitter.createDocuments([content]);
  
  // 2. Создать map-reduce chain
  const chain = loadSummarizationChain(llm, {
    type: "map_reduce",
    combinePrompt: mapPromptTemplate,
  });
  
  // 3. Запустить суммаризацию
  const summary = await chain.call({ input_documents: docs });
  
  return summary.text;
}
```

### Визуализация процесса

```
Исходный документ (100,000 токенов)
         │
         │ Split на чанки
         ▼
┌────────────────────────────────────────────────┐
│  Chunk 1   Chunk 2   Chunk 3   ...  Chunk 10  │
│  (10K tok) (10K tok) (10K tok)      (10K tok)  │
└────────────────────────────────────────────────┘
         │
         │ MAP: Суммаризировать каждый чанк параллельно
         ▼
┌────────────────────────────────────────────────┐
│  Summary 1 Summary 2 Summary 3 ... Summary 10 │
│  (500 tok) (500 tok) (500 tok)     (500 tok)  │
└────────────────────────────────────────────────┘
         │
         │ REDUCE: Объединить все суммари
         ▼
┌────────────────────────────────────────────────┐
│  Final Summary                                 │
│  (2000 токенов)                                │
└────────────────────────────────────────────────┘
```

**Преимущества:**
- ✅ Может обработать документы любого размера
- ✅ Параллельная обработка чанков (быстрее)
- ✅ Сохраняет ключевую информацию из всех частей

---

## 🤖 Где используется: Document Summarizer Plugin

### Plugin для агентов

```javascript
// server/utils/agents/aibitat/plugins/summarize.js

const docSummarizer = {
  name: "document-summarizer",
  plugin: function () {
    return {
      setup(aibitat) {
        aibitat.function({
          name: "document-summarizer",
          description: "Can get the list of files and summarize them",
          parameters: {
            action: "list" | "summarize",
            document_filename: "example.txt"
          },
          handler: async function ({ action, document_filename }) {
            if (action === "list") {
              return await this.listDocuments();  // Список документов
            }
            if (action === "summarize") {
              return await this.summarizeDoc(document_filename);  // Суммаризация
            }
          }
        });
      }
    };
  }
};
```

### Логика суммаризации

```javascript
summarizeDoc: async function (filename) {
  // 1. Найти документ в workspace
  const document = await Document.content(docInfo.document_id);
  
  // 2. Проверить размер
  const tokenCount = tokenManager.countFromString(document.content);
  const contextLimit = Provider.contextLimit(provider, model);
  
  // 3. Если влезает в контекст - вернуть как есть
  if (tokenCount < contextLimit) {
    return document.content;  // Полный текст
  }
  
  // 4. Если НЕ влезает - суммаризировать
  return await summarizeContent({
    provider: this.super.provider,
    model: this.super.model,
    content: document.content
  });
}
```

---

## 💡 Use Cases для суммаризации

### 1. **Агент запрашивает большой документ**

**Сценарий:**
```
User: "Расскажи про годовой отчет 2024"
  │
  ▼
Agent: Uses document-summarizer tool
  │
  ▼
Tool: Находит annual_report_2024.pdf (200 страниц, 50K токенов)
  │
  ▼
Check: 50K tokens > model context (16K)
  │
  ▼
Action: Map-Reduce суммаризация → 2K токенов
  │
  ▼
Agent: "Годовой отчет показывает рост выручки на 15%..."
```

### 2. **Обработка длинных документов**

**Примеры:**
- Технические спецификации (100+ страниц)
- Юридические договоры
- Научные статьи
- Протоколы совещаний (много встреч)

### 3. **Research agent workflow**

```javascript
// Пример: Research агент
aibitat
  .agent("researcher", {
    role: "You research topics and summarize findings"
  })
  .use(AgentPlugins.webBrowsing)       // Ищет информацию
  .use(AgentPlugins.docSummarizer);    // Суммаризирует найденное

// Workflow:
// 1. Web browsing → находит 10 статей
// 2. Document summarizer → суммаризирует каждую
// 3. Researcher → объединяет в финальный отчет
```

---

## 📊 Map-Reduce Summarization: Детали

### Что такое Map-Reduce?

```
MAP Phase (параллельно):
┌─────────────┐
│  Chunk 1    │──► LLM ──► Summary 1
└─────────────┘

┌─────────────┐
│  Chunk 2    │──► LLM ──► Summary 2
└─────────────┘

┌─────────────┐
│  Chunk 3    │──► LLM ──► Summary 3
└─────────────┘

REDUCE Phase (последовательно):
Summary 1 + Summary 2 + Summary 3
              │
              ▼ LLM
         Final Summary
```

### Промпт для суммаризации

```javascript
const mapPrompt = `
Write a detailed summary of the following text for a research purpose:
"{text}"
SUMMARY:
`;
```

**Параметры:**
- `temperature: 0` - детерминированный результат
- `chunkSize: 10000` - большие чанки (но влезают в контекст)
- `chunkOverlap: 500` - сохраняет контекст между чанками

---

## 🆚 Альтернативные подходы к суммаризации

### 1. **Refine (LangChain)**

```javascript
// Последовательная суммаризация
const chain = loadSummarizationChain(llm, {
  type: "refine"  // вместо map_reduce
});

// Процесс:
// Summary 1 = summarize(Chunk 1)
// Summary 2 = refine(Summary 1, Chunk 2)
// Summary 3 = refine(Summary 2, Chunk 3)
// ...
```

**Плюсы:**
- Более связный результат
- Лучше для нарративных текстов

**Минусы:**
- Медленнее (последовательная обработка)
- Дороже (больше LLM вызовов)

**AnythingLLM выбрал map_reduce:** быстрее и дешевле

---

### 2. **Stuff (простейший)**

```javascript
const chain = loadSummarizationChain(llm, {
  type: "stuff"  // Всё в один промпт
});
```

**Работает только если:** document < context limit

---

### 3. **Custom chunked approach**

Без LangChain:

```python
# Ваш подход (можно добавить)
async def summarize_large_document(text: str, max_tokens: int = 16000):
    """Суммаризация большого документа через чанкинг"""
    
    # 1. Разбить на чанки
    chunks = split_into_chunks(text, chunk_size=8000)
    
    # 2. Суммаризировать каждый чанк
    summaries = []
    for i, chunk in enumerate(chunks):
        prompt = f"Summarize the following text (part {i+1}/{len(chunks)}):\n\n{chunk}"
        summary = await call_llm(prompt)
        summaries.append(summary)
    
    # 3. Объединить суммари
    combined = "\n\n".join(summaries)
    
    # 4. Финальная суммаризация (если нужно)
    if count_tokens(combined) > max_tokens:
        final_prompt = f"Create a final summary from these summaries:\n\n{combined}"
        return await call_llm(final_prompt)
    
    return combined
```

---

## 🎯 Применение к вашему проекту

### Use Case 1: Суммаризация для RAG

**Проблема:** У вас есть длинные документы (email threads, technical docs)

**Решение:**
```python
# backend/services/summarization.py

async def summarize_for_context(chunks: List[str], query: str) -> str:
    """
    Суммаризировать чанки специально для запроса
    Вместо того чтобы давать все чанки в LLM - дать summary
    """
    
    # 1. Найти релевантные чанки (hybrid search)
    relevant_chunks = search(query, top_k=20)  # Больше чем обычно
    
    # 2. Если влезают в контекст - вернуть как есть
    total_tokens = sum(count_tokens(c) for c in relevant_chunks)
    if total_tokens < context_limit:
        return relevant_chunks
    
    # 3. Суммаризировать каждый чанк
    summaries = []
    for chunk in relevant_chunks:
        summary = await call_llm(
            f"Summarize this text focusing on: {query}\n\nText: {chunk}"
        )
        summaries.append(summary)
    
    return summaries  # Compressed context
```

**Польза:**
- ✅ Больше контекста в тот же context window
- ✅ Фокус на релевантной информации
- ✅ Лучшие ответы для широких вопросов

---

### Use Case 2: Суммаризация email threads

**У вас есть:** `email_correspondence` с длинными цепочками

**Можно добавить:**
```python
# backend/services/email_summarizer.py

async def summarize_email_thread(emails: List[str]) -> str:
    """
    Суммаризировать длинную email переписку
    """
    
    # 1. Объединить все emails
    thread = "\n\n---EMAIL---\n\n".join(emails)
    
    # 2. Проверить размер
    if count_tokens(thread) < 4000:
        return thread  # Короткая переписка
    
    # 3. Map-Reduce суммаризация
    # MAP: суммаризировать каждое письмо
    email_summaries = []
    for i, email in enumerate(emails):
        summary = await call_llm(
            f"Summarize this email (message {i+1}):\n{email}"
        )
        email_summaries.append(f"Message {i+1}: {summary}")
    
    # REDUCE: общая суммаризация треда
    combined = "\n\n".join(email_summaries)
    final_summary = await call_llm(
        f"Create a summary of this email thread:\n{combined}"
    )
    
    return final_summary
```

**Пример:**
```
Input: 50 emails в треде (30K токенов)
Output: Краткая суммаризация (1K токенов)

"Тред обсуждает проект миграции. Основные точки:
- Джон предложил использовать Kubernetes (15 марта)
- Команда согласовала бюджет $50K (18 марта)  
- Дедлайн перенесен на 1 июня (22 марта)
- Текущий статус: в разработке"
```

---

### Use Case 3: Tool для агентов (как в AnythingLLM)

**Добавить tool "summarize-document" для ботов:**

```python
# backend/services/agent_tools.py

class DocumentSummarizerTool(AgentTool):
    name = "summarize-document"
    description = "Summarize a document from the knowledge base"
    
    parameters = {
        "type": "object",
        "properties": {
            "doc_id": {
                "type": "string",
                "description": "Document ID to summarize"
            }
        }
    }
    
    async def execute(self, args: dict, context: AccessContext) -> str:
        doc_id = args["doc_id"]
        
        # 1. Получить документ (с ACL проверкой)
        chunks = get_document_chunks(doc_id, context)
        
        if not chunks:
            return "Document not found or no access"
        
        # 2. Объединить чанки
        full_text = "\n\n".join([c["text"] for c in chunks])
        
        # 3. Проверить размер
        if count_tokens(full_text) < 4000:
            return full_text  # Короткий документ
        
        # 4. Суммаризировать
        summary = await self.map_reduce_summarize(full_text)
        
        return summary
    
    async def map_reduce_summarize(self, text: str) -> str:
        """Map-Reduce суммаризация"""
        
        # MAP
        chunks = split_text(text, chunk_size=8000)
        summaries = []
        
        for i, chunk in enumerate(chunks):
            prompt = f"Summarize part {i+1}/{len(chunks)}:\n{chunk}"
            summary = await call_llm(prompt)
            summaries.append(summary)
        
        # REDUCE
        if len(summaries) == 1:
            return summaries[0]
        
        combined = "\n\n".join(summaries)
        final = await call_llm(
            f"Create final summary:\n{combined}"
        )
        
        return final
```

**Использование агентом:**

```
User: "@research_bot summarize the cloud migration plan"
  │
  ▼
Research Bot: Calls document-summarizer tool
  │
  ▼
Tool: 
  1. Находит "cloud_migration_plan.pdf" (50 страниц)
  2. Map-Reduce суммаризация
  3. Возвращает summary (500 слов)
  │
  ▼
Research Bot: "Cloud migration plan summary:
  - Budget: $200K
  - Timeline: 6 months
  - Technology: Kubernetes + AWS
  - Risks: Data migration complexity
  - Team: 5 engineers needed"
```

---

## 📊 Когда нужна суммаризация?

### ✅ Нужна ЕСЛИ:

1. **Документы > context limit**
   - Технические спецификации (100+ страниц)
   - Длинные email threads (50+ сообщений)
   - Большие протоколы

2. **Агенты работают с документами**
   - Research bot должен "прочитать" документ
   - Support bot нужен overview большого FAQ
   - Analytics bot анализирует отчеты

3. **Пользователь просит summary**
   - "Summarize last month's emails"
   - "Give me TL;DR of this document"
   - "What's in this 50-page spec?"

### ❌ НЕ нужна ЕСЛИ:

1. **Все документы короткие** (<4K токенов)
2. **Используете только search** (не full document access)
3. **RAG возвращает только релевантные чанки** (уже фильтровано)

---

## 🔧 Реализация для вашего проекта

### Вариант 1: Простая суммаризация (без LangChain)

```python
# backend/services/summarization.py

async def summarize_text(text: str, max_summary_tokens: int = 500) -> str:
    """
    Простая суммаризация через LLM
    """
    prompt = f"""Summarize the following text concisely in {max_summary_tokens} tokens or less:

{text}

SUMMARY:"""
    
    return await call_llm(prompt)


async def summarize_long_text(text: str, chunk_size: int = 8000) -> str:
    """
    Map-Reduce суммаризация для длинных текстов
    """
    tokens = count_tokens(text)
    
    # Если короткий - прямая суммаризация
    if tokens < chunk_size:
        return await summarize_text(text)
    
    # MAP: разбить и суммаризировать
    chunks = split_text_by_tokens(text, chunk_size)
    summaries = []
    
    for i, chunk in enumerate(chunks):
        print(f"Summarizing chunk {i+1}/{len(chunks)}...")
        summary = await summarize_text(chunk, max_summary_tokens=300)
        summaries.append(summary)
    
    # REDUCE: объединить суммари
    combined = "\n\n".join(summaries)
    
    # Финальная суммаризация если нужно
    if count_tokens(combined) > chunk_size:
        return await summarize_text(combined, max_summary_tokens=800)
    
    return combined
```

**Время реализации:** 1-2 дня  
**Зависимости:** Нет новых (используем существующий LLM)

---

### Вариант 2: С LangChain (более продвинутый)

```python
# backend/services/summarization_langchain.py

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.summarize import load_summarize_chain
from langchain.docstore.document import Document
from langchain_community.llms import Ollama  # или vLLM

async def summarize_with_langchain(text: str) -> str:
    """
    Map-Reduce суммаризация через LangChain
    """
    # 1. LLM
    llm = Ollama(base_url="http://ollama:11434", model="llama3.1:8b")
    
    # 2. Text splitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=10000,
        chunk_overlap=500,
        separators=["\n\n", "\n", ". ", " "]
    )
    
    # 3. Разбить на документы
    docs = splitter.create_documents([text])
    
    # 4. Суммаризация chain
    chain = load_summarize_chain(
        llm,
        chain_type="map_reduce",
        verbose=True
    )
    
    # 5. Запустить
    result = chain.run(docs)
    
    return result
```

**Время реализации:** 2-3 дня  
**Зависимости:** `langchain`, `langchain-community`

**Преимущества LangChain подхода:**
- ✅ Готовый map-reduce
- ✅ Оптимизированные промпты
- ✅ Retry logic
- ✅ Streaming support

**Недостатки:**
- ❌ Новая зависимость
- ❌ Больше overhead

---

## 💡 Рекомендации

### Для вашего проекта:

#### Этап 1: Простая суммаризация (1-2 дня)

```python
# Добавить в backend/services/summarization.py
async def summarize_long_text(text: str) -> str:
    # Map-Reduce без LangChain
```

**Использование:**
```python
# В RAG pipeline
if count_tokens(document) > context_limit:
    document = await summarize_long_text(document)

# RAG с суммаризированным контекстом
answer = call_llm(build_prompt(document, question))
```

---

#### Этап 2: Agent tool (2 дня)

```python
# Добавить в agent_tools.py
class SummarizeTool(AgentTool):
    name = "summarize-document"
    
    async def execute(self, args, context):
        doc_id = args["doc_id"]
        # Суммаризация с ACL проверкой
```

**Использование:**
```
User: "@research_bot summarize migration_plan.pdf"
Bot: Uses summarize-document tool
Bot: "Summary: ... [500 words]"
```

---

#### Этап 3: LangChain integration (опционально, 2-3 дня)

Если понадобится более продвинутая суммаризация:
- Refine chain для нарративных текстов
- Custom промпты для разных типов документов
- Streaming суммаризации

---

## 📈 Примеры из реальной жизни

### Пример 1: Email thread суммаризация

**Input:** 
```
Email thread: "Project Alpha Discussion" (30 emails, 15K tokens)
- От: John, Alice, Bob, Charlie
- Период: March 1-30, 2024
```

**Output (суммаризация):**
```
Summary of "Project Alpha Discussion":

Key Decisions:
• Budget approved: $150K (March 5)
• Technology stack: React + Python (March 12)
• Timeline: 6 months, deadline Sept 1 (March 18)

Action Items:
• John: Hire 2 developers (by March 31)
• Alice: Finalize architecture (by April 15)
• Bob: Setup CI/CD (by April 30)

Risks Identified:
• Tight timeline mentioned by Charlie (March 22)
• Potential vendor lock-in with AWS (March 25)

Status: In planning phase, team assembled
```

**Польза:**
- Пользователь видит суть за секунды
- Агент может использовать summary для принятия решений
- Экономия токенов для LLM

---

### Пример 2: Technical documentation

**Input:**
```
Document: "API Reference v2.0" (200 pages, 80K tokens)
```

**Map-Reduce процесс:**
```
MAP:
  Chunk 1 (pages 1-20)   → Summary: "Authentication section describes OAuth2..."
  Chunk 2 (pages 21-40)  → Summary: "REST endpoints for user management..."
  Chunk 3 (pages 41-60)  → Summary: "WebSocket API for real-time..."
  ... (10 chunks total)

REDUCE:
  All 10 summaries → "API v2.0 provides OAuth2 authentication, 
                      REST endpoints for CRUD, WebSocket for real-time,
                      rate limiting 1000 req/min, supports JSON/XML..."
```

**Output:** 2K токенов вместо 80K

---

### Пример 3: Multi-document research

**Запрос:** "Summarize all cloud migration documents"

**Процесс:**
```python
# 1. Найти все документы по теме
docs = search("cloud migration", doc_types=["technical_docs", "work_plans"])

# 2. Суммаризировать каждый
summaries = []
for doc in docs:
    summary = await summarize_document(doc.id)
    summaries.append({
        "doc_id": doc.id,
        "title": doc.title,
        "summary": summary
    })

# 3. Объединить в финальный report
report = await call_llm(f"""
Create a comprehensive report about cloud migration based on these summaries:

{json.dumps(summaries, indent=2)}

Focus on: timeline, budget, technologies, risks.
""")

return report
```

---

## 🎯 ИТОГОВОЕ ЗАКЛЮЧЕНИЕ

### Как используется суммаризация в AnythingLLM?

**Ответ:**

1. **Agent tool** - боты могут суммаризировать документы
2. **Fallback для больших документов** - если не влезает в контекст
3. **Map-Reduce через LangChain** - параллельная обработка чанков

### Зачем нужна суммаризация?

**3 основные причины:**

1. **Context window limits** - документ > model context
2. **Agent workflows** - боту нужен overview документа
3. **User experience** - "дай мне TL;DR"

### Стоит ли добавлять в ваш проект?

**Ответ:** ✅ **ДА, но сначала простой вариант**

**План:**

1. **Сейчас (1-2 дня):** Простая map-reduce без LangChain
   ```python
   async def summarize_long_text(text: str) -> str:
       # Custom implementation
   ```

2. **Потом (2 дня):** Agent tool для ботов
   ```python
   class SummarizeTool(AgentTool):
       # Tool для суммаризации
   ```

3. **Опционально:** LangChain integration если понадобится

**Польза:** ⭐⭐⭐⭐ Высокая (особенно для email threads и длинных docs)

**Документ:** `docs/SUMMARIZATION_USE_CASES.md`
