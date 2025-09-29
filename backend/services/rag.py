
import json
import requests
from typing import Dict, List

from .config import (
    CONTEXT_SNIPPET_MAX_CHARS,
    LLM_MAX_TOKENS,
    LLM_MODE,
    LLM_MODEL,
    LLM_STREAM_ENABLED,
    LLM_TIMEOUT,
)
from .context import compress_text

def build_prompt(context_items: List[Dict], question: str) -> str:
    ctx_lines = []
    for i, it in enumerate(context_items, 1):
        pl = it["payload"]
        raw_text = pl.get("text") or ""
        text = compress_text(raw_text, question)[:CONTEXT_SNIPPET_MAX_CHARS]
        ctx_lines.append(
            f"[{i}] doc_id={pl.get('doc_id')} chunk={pl.get('chunk_index')} type={pl.get('doc_type')}\n\"{text}\""
        )
    ctx = "\n\n".join(ctx_lines)
    return (
        "Ты — ассистент, отвечай строго по предоставленному КОНТЕКСТУ. "
        "Если данных недостаточно — так и скажи.\n\n"
        f"КОНТЕКСТ:\n{ctx}\n\n"
        f"ВОПРОС:\n{question}\n\n"
        "Ответь кратко и по делу. Если перечисляешь дедлайны — укажи дату и источник (doc_id/chunk)."
    )

def call_llm(prompt: str) -> str:
    if LLM_MODE == "ollama":
        try:
            r = requests.post(
                "http://ollama:11434/api/generate",
                json={
                    "model": LLM_MODEL,
                    "prompt": prompt,
                    "stream": LLM_STREAM_ENABLED,
                    "options": {"num_predict": LLM_MAX_TOKENS},
                },
                timeout=LLM_TIMEOUT,
                stream=LLM_STREAM_ENABLED,
            )
            r.raise_for_status()
            if LLM_STREAM_ENABLED:
                parts = []
                buffer = ""
                for raw_line in r.iter_lines(decode_unicode=True):
                    if raw_line is None:
                        continue
                    line = buffer + raw_line
                    buffer = ""
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        buffer = line
                        continue
                    chunk = data.get("response")
                    if chunk:
                        parts.append(chunk)
                    if data.get("done"):
                        break
                return "".join(parts).strip()
            return r.json().get("response", "")
        except Exception as e:
            return f"[LLM ошибка: {e}]"
    return "[LLM выключена]"
