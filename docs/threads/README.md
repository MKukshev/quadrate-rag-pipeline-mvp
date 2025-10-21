# Thread Files Directory

This directory contains conversation thread files for testing and demonstration.

## Supported Formats

### Email Threads
Place `.txt` files with standard email format:
```
From: Alice <alice@example.com>
Date: Mon, 10 Jan 2025 10:00:00
To: Bob <bob@example.com>
Subject: Project Discussion

Message body...
```

### Telegram Exports
Place Telegram chat exports:
```
[10.01.2025, 10:00] Alice: Message text
[10.01.2025, 10:05] Bob: Reply text
```

### WhatsApp Exports
Place WhatsApp chat exports:
```
10/01/2025, 10:00 - Alice: Message text
10/01/2025, 10:05 - Bob: Reply text
```

## Usage

```bash
# Upload email thread
curl -X POST http://localhost:8000/ingest-thread \
  -F "file=@docs/threads/email_thread.txt" \
  -F "space_id=demo" \
  -F "thread_type=email" \
  -F "auto_summarize=true"

# Upload telegram chat
curl -X POST http://localhost:8000/ingest-thread \
  -F "file=@docs/threads/telegram_chat.txt" \
  -F "space_id=demo" \
  -F "thread_type=telegram"
```

## Existing Files

You can also process existing thread files from:
- `docs/email_correspondence/` - Email threads
- `docs/messenger_correspondence/` - Telegram/WhatsApp chats

