# Анализ парсеров документов AnythingLLM

## 🎯 Задача
Проанализировать [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) и оценить возможность интеграции их парсеров документов в текущий RAG-пайплайн.

---

## 📊 Сравнительная таблица: Текущий пайплайн vs AnythingLLM

| Формат | Текущий пайплайн | AnythingLLM | Преимущества AnythingLLM |
|--------|------------------|-------------|--------------------------|
| **PDF** | PyMuPDF + pdfplumber | pdf-parse + OCR (Tesseract.js) | ✅ OCR для сканов, fallback логика |
| **DOCX** | python-docx | Langchain DocxLoader | ✅ Та же библиотека (mammoth) |
| **XLSX/CSV** | pandas + openpyxl | node-xlsx | ≈ Похожие возможности |
| **TXT/MD** | decode utf-8 | fs.readFile | ≈ Идентично |
| **Images** | ❌ Нет поддержки | Tesseract.js OCR | ✅ **НОВОЕ**: PNG, JPG, WebP |
| **Audio** | ❌ Нет поддержки | Whisper (local/OpenAI) | ✅ **НОВОЕ**: MP3, WAV, M4A |
| **EPUB** | ❌ Нет поддержки | Langchain EPubLoader | ✅ **НОВОЕ**: Электронные книги |
| **MBOX** | ❌ Нет поддержки | mbox-parser | ✅ **НОВОЕ**: Email архивы |
| **PPTX** | ❌ Нет поддержки | officeparser | ✅ **НОВОЕ**: PowerPoint |
| **ODT/ODP** | ❌ Нет поддержки | officeparser | ✅ **НОВОЕ**: LibreOffice |
| **HTML** | ❌ Нет поддержки | html-to-text | ✅ **НОВОЕ**: Web pages |
| **JSON** | ❌ Нет поддержки | JSON.parse | ✅ **НОВОЕ**: Structured data |

---

## 🔧 Технологии AnythingLLM

### Парсинг библиотеки (из package.json)

```json
{
  // PDF
  "pdf-parse": "^1.1.1",           // Парсинг цифровых PDF
  "tesseract.js": "^6.0.0",        // OCR для сканов
  "sharp": "^0.33.5",              // Обработка изображений
  
  // Office документы
  "mammoth": "^1.6.0",             // DOCX (через Langchain)
  "node-xlsx": "^0.24.0",          // Excel
  "officeparser": "^4.0.5",        // PPTX, ODT, ODP
  
  // Другие форматы
  "epub2": "^3.0.2",               // Электронные книги
  "mbox-parser": "^1.0.1",         // Email архивы
  "html-to-text": "^9.0.5",        // HTML страницы
  
  // Audio
  "fluent-ffmpeg": "^2.1.2",       // Конвертация аудио
  "wavefile": "^11.0.0",           // WAV обработка
  
  // Langchain
  "@langchain/community": "^0.2.23",
  "langchain": "0.1.36",
  
  // Утилиты
  "js-tiktoken": "^1.0.8",         // Подсчет токенов
  "slugify": "^1.6.6"              // URL-safe имена
}
```

---

## 🆚 Детальное сравнение

### 1. PDF Parsing

#### Текущий пайплайн
```python
# backend/services/parsers.py
import fitz  # PyMuPDF
import pdfplumber

def parse_pdf_bytes(data: bytes) -> str:
    # 1. PyMuPDF для markdown
    # 2. Fallback на pdfplumber для текста
```

**Библиотеки:**
- `pymupdf>=1.24` - основной парсер
- `pdfplumber>=0.11` - fallback

#### AnythingLLM
```javascript
// collector/processSingleFile/convert/asPDF/index.js
const PDFLoader = require("./PDFLoader");
const OCRLoader = require("../../../utils/OCRLoader");

async function asPdf(file) {
  let docs = await pdfLoader.load();  // pdf-parse
  
  // Если пусто - пробуем OCR
  if (docs.length === 0) {
    docs = await OCRLoader.ocrPDF(fullFilePath);  // Tesseract.js
  }
}
```

**Библиотеки:**
- `pdf-parse` - основной парсер (pdf.js v1.10.100)
- `tesseract.js` - OCR для сканированных PDF
- `sharp` - обработка изображений

**✅ Преимущества AnythingLLM:**
- **OCR поддержка** - автоматический fallback на Tesseract для сканов
- **Параллельная обработка** - worker pool для быстрого OCR
- **Batch processing** - обработка страниц батчами

**❌ Недостатки:**
- JavaScript зависимости (vs чистый Python)
- Больше памяти для OCR (Tesseract workers)

---

### 2. DOCX Parsing

#### Текущий пайплайн
```python
from docx import Document

def parse_docx_bytes(data: bytes) -> str:
    d = Document(io.BytesIO(data))
    # Обработка параграфов, заголовков, списков
```

**Библиотека:** `python-docx>=1.1`

#### AnythingLLM
```javascript
const { DocxLoader } = require("langchain/document_loaders/fs/docx");

// Использует mammoth под капотом
const loader = new DocxLoader(fullFilePath);
const docs = await loader.load();
```

**Библиотека:** `mammoth` (через Langchain)

**≈ Сравнение:**
- Обе библиотеки работают похоже
- python-docx чуть более гибкая
- mammoth проще в использовании
- **Вывод:** Интеграция не даст значительных улучшений

---

### 3. Excel/CSV Parsing

#### Текущий пайплайн
```python
import pandas as pd

def parse_xlsx_bytes(data: bytes) -> str:
    xls = pd.ExcelFile(io.BytesIO(data))
    # Конвертация в markdown таблицы
```

**Библиотеки:** `pandas>=2.2`, `openpyxl>=3.1`

#### AnythingLLM
```javascript
const xlsx = require("node-xlsx").default;

const workSheetsFromFile = xlsx.parse(fullFilePath);
// Конвертация в CSV
```

**Библиотека:** `node-xlsx`

**≈ Сравнение:**
- pandas более мощный (фильтры, анализ)
- node-xlsx более простой
- **Вывод:** Текущее решение лучше

---

### 4. **НОВЫЕ форматы в AnythingLLM**

#### 4.1. Images (OCR) ✨

```javascript
// asImage.js
const OCRLoader = require("../../utils/OCRLoader");

async function asImage({ fullFilePath }) {
  let content = await new OCRLoader({
    targetLanguages: options?.ocr?.langList  // eng, rus, deu, fra...
  }).ocrImage(fullFilePath);
  
  return content;  // Извлеченный текст
}
```

**Поддерживаемые форматы:**
- PNG, JPG, JPEG, WebP, TIFF, BMP

**Библиотеки:**
- `tesseract.js` - OCR engine
- `sharp` - обработка изображений

**Use cases:**
- Сканы документов
- Скриншоты
- Инфографика
- Диаграммы

#### 4.2. Audio (Транскрипция) ✨

```javascript
// asAudio.js
const { LocalWhisper } = require("../../utils/WhisperProviders/localWhisper");
const { OpenAiWhisper } = require("../../utils/WhisperProviders/OpenAiWhisper");

async function asAudio({ fullFilePath }) {
  const whisper = new LocalWhisper();  // или OpenAI
  const { content } = await whisper.processFile(fullFilePath);
  
  return content;  // Транскрипция
}
```

**Поддерживаемые форматы:**
- MP3, WAV, M4A, FLAC, OGG

**Провайдеры:**
- **Local Whisper** - через whisper.cpp или transformers
- **OpenAI Whisper** - через API

**Use cases:**
- Совещания/встречи
- Лекции
- Подкасты
- Голосовые заметки

#### 4.3. EPUB (Электронные книги) ✨

```javascript
// asEPub.js
const { EPubLoader } = require("langchain/document_loaders/fs/epub");

const loader = new EPubLoader(fullFilePath, { splitChapters: false });
const docs = await loader.load();
```

**Библиотека:** `epub2` (через Langchain)

**Use cases:**
- Техническая документация в формате книг
- Обучающие материалы
- Руководства

#### 4.4. MBOX (Email архивы) ✨

```javascript
// asMbox.js
const { mboxParser } = require("mbox-parser");

const mails = await mboxParser(fs.createReadStream(fullFilePath));
// Каждое письмо - отдельный документ
```

**Библиотека:** `mbox-parser`

**Use cases:**
- Gmail/Outlook экспорт
- Архивы переписки
- Email бэкапы

**Особенность:** Разбивает по отдельным сообщениям (vs текущий txt подход)

#### 4.5. PowerPoint (PPTX) ✨

```javascript
// asOfficeMime.js
const officeParser = require("officeparser");

const content = await officeParser.parseOfficeAsync(fullFilePath);
```

**Библиотека:** `officeparser`

**Поддерживает:**
- PPTX, PPT
- ODT (OpenDocument Text)
- ODP (OpenDocument Presentation)

**Use cases:**
- Презентации
- Слайды
- LibreOffice документы

#### 4.6. HTML ✨

```javascript
// constants.js
".html": "./convert/asTxt.js",

// Используется html-to-text для конвертации
```

**Библиотека:** `html-to-text`

**Use cases:**
- Веб-страницы
- Экспортированные статьи
- Documentation сайты

---

## 💡 Ключевые отличия архитектуры

### AnythingLLM подход

```javascript
// NodeJS микросервисная архитектура
collector/  
├── processSingleFile/    // Обработка одного файла
│   └── convert/
│       ├── asPDF.js      // Специализированный парсер
│       ├── asDocx.js
│       └── asImage.js
├── processLink/          // Обработка URL
└── processRawText/       // Обработка текста

// Каждый конвертер возвращает унифицированный формат:
{
  id: uuid,
  pageContent: string,
  token_count_estimate: number,
  metadata: {...}
}
```

### Текущий пайплайн

```python
# Python монолитный подход
backend/services/
└── parsers.py            // Все парсеры в одном файле
    ├── parse_pdf_bytes()
    ├── parse_docx_bytes()
    ├── parse_xlsx_bytes()
    └── parse_txt_bytes()

# Возвращает просто строку
return markdown_text
```

---

## 🔍 Детальная оценка интеграции

### ✅ Стоит интегрировать

#### 1. **OCR для изображений и PDF** ⭐⭐⭐⭐⭐
**Приоритет:** Высокий

**Что добавляет:**
- Извлечение текста из скриншотов
- Обработка сканированных PDF
- Поддержка изображений (PNG, JPG)

**Технология AnythingLLM:**
```javascript
tesseract.js + sharp
- Multi-threaded OCR (4 workers по умолчанию)
- Batch processing (10 страниц за раз)
- Поддержка 100+ языков
```

**Python аналог:**
```python
# Можно интегрировать:
pytesseract + Pillow
# или
easyocr (GPU-accelerated)
# или
paddleocr (быстрее Tesseract)
```

**Рекомендация:** ✅ Добавить OCR поддержку в parsers.py

---

#### 2. **Audio транскрипция** ⭐⭐⭐⭐
**Приоритет:** Средний-Высокий

**Что добавляет:**
- Транскрипция аудио записей совещаний
- Обработка голосовых заметок
- Индексация подкастов/лекций

**Технология AnythingLLM:**
```javascript
Whisper (OpenAI API или local)
- Поддержка MP3, WAV, M4A
- ffmpeg для конвертации
```

**Python аналог:**
```python
# Варианты:
1. openai-whisper (official, CPU/GPU)
2. faster-whisper (CTranslate2, 4x быстрее)
3. whisper.cpp (C++, очень быстрый)
```

**Рекомендация:** ✅ Добавить Whisper для аудио

---

#### 3. **EPUB (Электронные книги)** ⭐⭐⭐
**Приоритет:** Средний

**Что добавляет:**
- Техническая документация в формате книг
- Обучающие материалы

**Технология AnythingLLM:**
```javascript
epub2 (через Langchain)
```

**Python аналог:**
```python
ebooklib или epub
```

**Рекомендация:** ✅ Полезно для technical_docs

---

#### 4. **MBOX (Email архивы)** ⭐⭐⭐⭐
**Приоритет:** Высокий (учитывая наличие email_correspondence)

**Что добавляет:**
- Импорт Gmail/Outlook экспортов
- Обработка email архивов
- Разделение по отдельным сообщениям

**Технология AnythingLLM:**
```javascript
mbox-parser
- Парсит каждое письмо отдельно
- Сохраняет From, Subject, Date
```

**Python аналог:**
```python
mailbox (стандартная библиотека Python!)
```

**Рекомендация:** ✅✅ Обязательно добавить (у вас есть email переписка!)

---

#### 5. **PowerPoint (PPTX)** ⭐⭐⭐
**Приоритет:** Средний

**Что добавляет:**
- Презентации
- Слайды

**Технология AnythingLLM:**
```javascript
officeparser
- Извлекает текст из PPTX
- Поддержка ODP (LibreOffice)
```

**Python аналог:**
```python
python-pptx
```

**Рекомендация:** ✅ Полезно для presentations категории

---

### ≈ Можно не интегрировать (уже есть или не нужно)

#### 6. **HTML** ⭐⭐
**Причина:** Простая конвертация, можно добавить легко

```python
# Python аналог (одна строка):
from html2text import html2text
```

#### 7. **JSON** ⭐
**Причина:** Слишком специфичный формат, не общего назначения

---

## 📦 Архитектурные отличия

### AnythingLLM: Микросервисы (NodeJS)

```
┌─────────────────────────────────────────┐
│  Frontend (React)                       │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│  Server (NodeJS)                        │
│  - API endpoints                        │
│  - Vector DB управление                 │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│  Collector (NodeJS) ← Отдельный сервис! │
│  - Парсинг документов                   │
│  - OCR                                  │
│  - Whisper                              │
└─────────────────────────────────────────┘
```

### Текущий пайплайн: Монолит (Python)

```
┌─────────────────────────────────────────┐
│  Backend (FastAPI)                      │
│  - API endpoints                        │
│  - Парсинг документов ← Всё в одном     │
│  - Vector DB управление                 │
│  - RAG логика                           │
└─────────────────────────────────────────┘
```

---

## 🎯 Рекомендации по интеграции

### Вариант 1: Полная интеграция (сложно)

Портировать все парсеры AnythingLLM в Python:

**Плюсы:**
- ✅ Все форматы
- ✅ Единый стек (Python)

**Минусы:**
- ❌ Много работы (2-3 недели)
- ❌ Нужно портировать logic
- ❌ Поддерживать параллельно

**Оценка:** 🔴 Не рекомендуется (слишком затратно)

---

### Вариант 2: Селективная интеграция (рекомендуется) ⭐

Добавить только **самые полезные** парсеры в Python:

#### Высокий приоритет:

1. **OCR для изображений** (pytesseract или easyocr)
   ```python
   # backend/services/parsers.py
   def parse_image_bytes(data: bytes) -> str:
       import pytesseract
       from PIL import Image
       image = Image.open(io.BytesIO(data))
       return pytesseract.image_to_string(image, lang='eng+rus')
   ```
   **Время:** 1-2 дня

2. **MBOX email parser** (mailbox стандартная библиотека!)
   ```python
   import mailbox
   
   def parse_mbox_bytes(data: bytes) -> str:
       mbox = mailbox.mbox(io.BytesIO(data))
       texts = []
       for message in mbox:
           texts.append(f"From: {message['from']}\n{message.get_payload()}")
       return "\n\n---\n\n".join(texts)
   ```
   **Время:** 1 день

3. **Audio транскрипция** (faster-whisper)
   ```python
   def parse_audio_bytes(file_path: str) -> str:
       from faster_whisper import WhisperModel
       model = WhisperModel("base")
       segments, _ = model.transcribe(file_path)
       return " ".join([seg.text for seg in segments])
   ```
   **Время:** 2-3 дня

4. **EPUB** (ebooklib)
   ```python
   def parse_epub_bytes(data: bytes) -> str:
       import ebooklib
       from ebooklib import epub
       book = epub.read_epub(io.BytesIO(data))
       # Извлечь текст из глав
   ```
   **Время:** 1 день

5. **PPTX** (python-pptx)
   ```python
   def parse_pptx_bytes(data: bytes) -> str:
       from pptx import Presentation
       prs = Presentation(io.BytesIO(data))
       texts = []
       for slide in prs.slides:
           for shape in slide.shapes:
               if hasattr(shape, "text"):
                   texts.append(shape.text)
       return "\n\n".join(texts)
   ```
   **Время:** 1 день

**Итого время:** 6-9 дней

**Зависимости для добавления:**
```python
# requirements.txt
pytesseract>=0.3.10      # OCR
Pillow>=10.0             # Images
faster-whisper>=1.0      # Audio transcription
ebooklib>=0.18           # EPUB
python-pptx>=0.6.23      # PowerPoint
```

---

### Вариант 3: Гибридная архитектура (сложно, но гибко)

Запустить AnythingLLM Collector как отдельный сервис:

```yaml
# docker-compose.yml
services:
  collector:
    build: ../anything-llm/collector
    ports: ["8500:8500"]
  
  backend:
    environment:
      - COLLECTOR_URL=http://collector:8500
```

**Плюсы:**
- ✅ Все парсеры AnythingLLM из коробки
- ✅ Не нужно портировать
- ✅ Обновления автоматически

**Минусы:**
- ❌ Два стека (Python + NodeJS)
- ❌ Сложность деплоя
- ❌ Больше памяти

**Оценка:** 🟡 Возможно, но усложняет архитектуру

---

## 📊 Итоговая таблица рекомендаций

| Формат | Приоритет | Сложность | Время | Библиотека Python | Рекомендация |
|--------|-----------|-----------|-------|-------------------|--------------|
| **OCR Images** | ⭐⭐⭐⭐⭐ | Низкая | 1-2 дня | `pytesseract` или `easyocr` | ✅ Добавить |
| **MBOX emails** | ⭐⭐⭐⭐⭐ | Низкая | 1 день | `mailbox` (встроенная!) | ✅ Добавить |
| **Audio (Whisper)** | ⭐⭐⭐⭐ | Средняя | 2-3 дня | `faster-whisper` | ✅ Добавить |
| **PPTX** | ⭐⭐⭐ | Низкая | 1 день | `python-pptx` | ✅ Добавить |
| **EPUB** | ⭐⭐⭐ | Низкая | 1 день | `ebooklib` | ✅ Добавить |
| **HTML** | ⭐⭐ | Низкая | 0.5 дня | `html2text` | 🟡 Опционально |
| **JSON** | ⭐ | Низкая | 0.5 дня | `json` (встроенный) | 🟡 Опционально |

---

## 📈 Влияние на текущую систему

### Обновление parsers.py

```python
# backend/services/parsers.py

# Добавить новые функции:
def parse_image_bytes(data: bytes) -> str:
    """OCR для изображений"""
    
def parse_audio_file(file_path: str) -> str:
    """Whisper транскрипция"""
    
def parse_mbox_bytes(data: bytes) -> List[str]:
    """MBOX email парсинг, возвращает список сообщений"""
    
def parse_epub_bytes(data: bytes) -> str:
    """EPUB книги"""
    
def parse_pptx_bytes(data: bytes) -> str:
    """PowerPoint презентации"""
```

### Обновление app.py

```python
# backend/app.py
from services.parsers import (
    parse_pdf_bytes,
    parse_docx_bytes,
    parse_xlsx_bytes,
    parse_txt_bytes,
    parse_image_bytes,     # NEW
    parse_audio_file,      # NEW
    parse_mbox_bytes,      # NEW
    parse_epub_bytes,      # NEW
    parse_pptx_bytes,      # NEW
)

# В config.py обновить:
ALLOWED_EXT = {
    ".txt", ".md", ".pdf", ".docx", ".xlsx", ".csv",
    ".png", ".jpg", ".jpeg", ".webp",  # Images
    ".mp3", ".wav", ".m4a",            # Audio
    ".mbox",                           # Email
    ".epub",                           # Books
    ".pptx",                           # Presentations
}
```

---

## 💰 Сравнение затрат

### Вариант A: Селективная интеграция (рекомендуется)

**Время разработки:** 6-9 дней  
**Новые зависимости:** 5-6 библиотек  
**Размер Docker image:** +500MB (из-за Tesseract)  
**Память runtime:** +1-2GB (для OCR/Whisper)  
**Поддержка:** Низкая (стандартные Python библиотеки)

**Результат:**
- ✅ 5 новых форматов
- ✅ OCR для сканов
- ✅ Audio транскрипция
- ✅ Единый Python стек

---

### Вариант B: Гибридная (AnythingLLM Collector сервис)

**Время разработки:** 2-3 дня (интеграция)  
**Новые зависимости:** NodeJS, npm  
**Размер Docker image:** +1.5GB (NodeJS + зависимости)  
**Память runtime:** +500MB (Collector сервис)  
**Поддержка:** Средняя (зависимость от AnythingLLM)

**Результат:**
- ✅ Все форматы AnythingLLM
- ✅ Автоматические обновления
- ❌ Два стека (Python + NodeJS)
- ❌ Сложнее деплой

---

## 🎯 Финальное заключение

### ✅ Рекомендация: Вариант 2 (Селективная интеграция)

**Добавить в приоритете:**

1. **MBOX parser** (1 день) - критично для email_correspondence
2. **OCR Images** (2 дня) - сканы документов
3. **PPTX parser** (1 день) - для presentations категории
4. **Audio Whisper** (3 дня) - для messenger_correspondence (голосовые)
5. **EPUB parser** (1 день) - для technical_docs

**Итого:** 8 дней разработки

**Новые зависимости:**
```python
# requirements.txt
pytesseract>=0.3.10      # или easyocr>=1.7
Pillow>=10.0
faster-whisper>=1.0      # или openai-whisper
ebooklib>=0.18
python-pptx>=0.6.23
```

**Результат:**
- +5 новых форматов
- OCR для сканов и изображений
- Аудио транскрипция
- Лучшая работа с email архивами
- Полная совместимость с существующей архитектурой

---

### ❌ НЕ рекомендуется интегрировать

1. **Замена PDF парсера** - текущий (PyMuPDF) лучше
2. **Замена DOCX парсера** - текущий достаточно хорош
3. **Замена Excel парсера** - pandas мощнее
4. **Полный переход на NodeJS** - нарушит архитектуру
5. **HTML/JSON парсеры** - низкий приоритет

---

## 📚 Дополнительно

### Интересные находки из AnythingLLM

1. **OCR Batching:** Worker pool из 4 потоков для параллельной обработки страниц
2. **Timeout management:** 5 минут на OCR одного PDF
3. **Fallback логика:** Если основной парсер не сработал → OCR
4. **Metadata extraction:** Автор, дата создания, word count

### Можно адаптировать

```python
# Идея из AnythingLLM: OCR fallback для PDF
def parse_pdf_bytes(data: bytes) -> str:
    try:
        # Основной парсер
        return pymupdf_parse(data)
    except EmptyTextException:
        # Fallback на OCR если текста нет
        return ocr_pdf(data)
```

---

## 🎉 Итоговое заключение

### Ответ на ваш вопрос:

**Да, можно и нужно интегрировать!** Но не всё, а селективно:

✅ **Обязательно:**
- MBOX parser (email архивы) - у вас уже есть email категория
- OCR для изображений - критично для сканов

✅ **Желательно:**
- Audio (Whisper) - для голосовых сообщений
- PPTX - для presentations категории
- EPUB - для technical_docs

❌ **Не нужно:**
- Замена PDF/DOCX/Excel парсеров - текущие лучше
- HTML/JSON - низкий приоритет

**Оценка работ:** 6-9 дней  
**Сложность:** Средняя  
**Польза:** Высокая (5 новых форматов)

