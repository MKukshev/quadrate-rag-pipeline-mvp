# Суммаризация документов - Quick Start

## 🚀 Быстрый старт (2 минуты)

### 1. Загрузить документ
```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@your_document.pdf" \
  -F "space_id=demo" | jq
```

Сохраните `doc_id` из ответа.

### 2. Суммаризировать
```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "your_doc_id_here",
    "space_id": "demo"
  }' | jq
```

### 3. Результат
```json
{
  "doc_id": "migration_plan_xyz",
  "space_id": "demo",
  "summary": "Cloud migration plan: Budget $200K, Timeline 6 months (Jan-Jun 2025), Technologies: Kubernetes + AWS, Team: 5 engineers, Main risk: data migration complexity",
  "chunks_processed": 15,
  "focus": null
}
```

---

## 🎯 С фокусом на конкретной теме

```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "your_doc_id",
    "space_id": "demo",
    "focus": "budget and costs"
  }' | jq
```

**Результат:** Суммаризация будет сфокусирована только на бюджете.

---

## 🧪 Автоматический тест

```bash
make test-summarization
```

Запустит полный тест:
- ✅ Загрузка документа
- ✅ Базовая суммаризация
- ✅ Суммаризация с фокусом
- ✅ Обработка ошибок

---

## 📊 Как это работает

### Для малых документов (< 8K токенов)
```
Document → LLM → Summary
Time: 2-5 секунд
```

### Для больших документов (> 8K токенов)
```
Document (50K токенов)
    ↓ Split на чанки
[Ch1] [Ch2] [Ch3] [Ch4] [Ch5] [Ch6]
    ↓ MAP: Суммаризировать каждый
[S1]  [S2]  [S3]  [S4]  [S5]  [S6]
    ↓ REDUCE: Объединить
Final Summary (500 токенов)

Time: 20-30 секунд
```

---

## 💡 Use Cases

### 1. Длинные документы
```bash
# Technical spec (100 страниц)
curl -X POST http://localhost:8000/summarize \
  -d '{"doc_id":"tech_spec","space_id":"demo"}'
```

### 2. Email threads
```bash
# Email переписка (50 сообщений)
curl -X POST http://localhost:8000/summarize \
  -d '{"doc_id":"email_thread_001","space_id":"demo","focus":"decisions made"}'
```

### 3. Reports
```bash
# Квартальный отчет
curl -X POST http://localhost:8000/summarize \
  -d '{"doc_id":"q4_report","space_id":"demo","focus":"key metrics"}'
```

---

## 📚 API Documentation

Полная документация доступна в Swagger UI:
```
http://localhost:8000/docs
```

Найдите `POST /summarize` в списке endpoints.

---

## 🔧 Конфигурация (опционально)

Добавьте в `.env` для тонкой настройки:

```bash
SUMMARIZATION_CHUNK_SIZE=8000          # Размер чанка для Map-Reduce
SUMMARIZATION_MAX_SUMMARY_TOKENS=500   # Максимум токенов в summary
```

По умолчанию работает отлично без дополнительной настройки!

