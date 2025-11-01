
import json
import requests
import time
from typing import Dict, List, Optional
from datetime import datetime

from .config import (
    CONTEXT_SNIPPET_MAX_CHARS,
    LLM_MAX_TOKENS,
    LLM_MODE,
    LLM_MODEL,
    LLM_STREAM_ENABLED,
    LLM_TIMEOUT,
    OLLAMA_NUM_CTX,
)
from .context import compress_text
from .llm_config import get_current_model_config


def calculate_dynamic_max_tokens(prompt: str, context_window: int, safety_margin: int = 500, verbose: bool = True) -> int:
    """
    Динамически рассчитывает max_tokens на основе размера промпта и контекстного окна
    
    Args:
        prompt: Текст промпта
        context_window: Размер контекстного окна модели
        safety_margin: Запас для системного промпта и безопасности
        verbose: Выводить ли детальную информацию
    
    Returns:
        Рекомендуемое значение max_tokens
    """
    prompt_tokens = len(prompt.split())
    available = context_window - prompt_tokens - safety_margin
    raw_result = min(available, 4096)  # Ограничиваем максимумом
    final_result = max(256, raw_result)  # Минимум 256 токенов
    
    if verbose:
        print(f"\n{'─'*80}")
        print(f"[DYNAMIC MAX_TOKENS CALCULATION]")
        print(f"📐 Formula: available = context_window - prompt_tokens - safety_margin")
        print(f"           result = max(256, min(available, 4096))")
        print(f"📊 Values:")
        print(f"  context_window  = {context_window:>6,} tokens")
        print(f"  prompt_tokens   = {prompt_tokens:>6,} tokens")
        print(f"  safety_margin   = {safety_margin:>6,} tokens")
        print(f"  available       = {available:>6,} tokens")
        print(f"  min(available, 4096) = {raw_result:>6,} tokens")
        print(f"  max(256, {raw_result:,})     = {final_result:>6,} tokens")
        print(f"✅ Result: {final_result:,} tokens")
        if available < 256:
            print(f"  ⚠️  WARNING: Available space ({available}) < minimum (256)!")
        elif available < 512:
            print(f"  ⚠️  WARNING: Very little space ({available}) for response!")
        usage_percent = (prompt_tokens / context_window) * 100
        print(f"  📊 Context usage: {usage_percent:.1f}% ({prompt_tokens:,}/{context_window:,})")
        print(f"{'─'*80}\n")
    
    return final_result

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

def call_llm(prompt: str, max_tokens: Optional[int] = None) -> str:
    request_start = datetime.now()
    start_time = time.time()
    prompt_tokens = len(prompt.split())
    prompt_chars = len(prompt)
    
    if LLM_MODE == "ollama":
        # Динамический расчет max_tokens
        model_config = get_current_model_config()
        if max_tokens is None:
            dynamic_max = calculate_dynamic_max_tokens(prompt, model_config.context_window, verbose=True)
            num_predict = dynamic_max
        else:
            num_predict = max_tokens
        
        print(f"\n{'='*80}")
        print(f"[LLM REQUEST → Ollama] Model: {LLM_MODEL}")
        print(f"📝 INPUT:")
        print(f"  - Prompt length: {prompt_chars} chars, ~{prompt_tokens} tokens")
        print(f"  - Max output tokens: {num_predict}")
        print(f"  - Context window: {OLLAMA_NUM_CTX}")
        print(f"  - Timeout: {LLM_TIMEOUT}s")
        print(f"  ⏰ Request time: {request_start.strftime('%H:%M:%S.%f')[:-3]}")
        print(f"🚀 Sending request to Ollama...")
        llm_send_time = datetime.now()
        print(f"  ⏰ LLM send time: {llm_send_time.strftime('%H:%M:%S.%f')[:-3]}")
        
        try:
            r = requests.post(
                "http://ollama:11434/api/generate",
                json={
                    "model": LLM_MODEL,
                    "prompt": prompt,
                    "stream": LLM_STREAM_ENABLED,
                    "options": {"num_predict": num_predict},
                },
                timeout=LLM_TIMEOUT,
                stream=LLM_STREAM_ENABLED,
            )
            r.raise_for_status()
            
            llm_receive_time = datetime.now()
            elapsed_time = time.time() - start_time
            
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
                response_text = "".join(parts).strip()
            else:
                response_text = r.json().get("response", "")
            
            response_tokens = len(response_text.split())
            response_chars = len(response_text)
            
            print(f"✅ Response received from Ollama!")
            print(f"  ⏰ LLM receive time: {llm_receive_time.strftime('%H:%M:%S.%f')[:-3]}")
            print(f"[LLM RESPONSE ← Ollama]")
            print(f"📤 OUTPUT:")
            print(f"  - Response length: {response_chars} chars, ~{response_tokens} tokens")
            print(f"  - Generation time: {elapsed_time:.2f}s")
            print(f"  - Speed: ~{response_tokens/elapsed_time:.1f} tokens/sec" if elapsed_time > 0 else "  - Speed: N/A")
            print(f"⏱️  TIMING BREAKDOWN:")
            print(f"  - Request start:  {request_start.strftime('%H:%M:%S.%f')[:-3]}")
            print(f"  - LLM send:       {llm_send_time.strftime('%H:%M:%S.%f')[:-3]}")
            print(f"  - LLM receive:    {llm_receive_time.strftime('%H:%M:%S.%f')[:-3]}")
            print(f"  - Total:          {elapsed_time:.3f}s")
            print(f"RESPONSE PREVIEW (first 500 chars):")
            print(f"{response_text[:500]}...")
            print(f"{'='*80}\n")
            
            return response_text
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"❌ LLM ERROR after {elapsed_time:.3f}s: {e}")
            print(f"{'='*80}\n")
            return f"[LLM ошибка: {e}]"
    
    elif LLM_MODE == "vllm":
        # Import vLLM support
        try:
            from .rag_vllm import call_vllm
            kwargs = {}
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            
            print(f"\n{'='*80}")
            print(f"[LLM REQUEST → vLLM] Model: {LLM_MODEL}")
            print(f"📝 INPUT:")
            print(f"  - Prompt length: {prompt_chars} chars, ~{prompt_tokens} tokens")
            if max_tokens:
                print(f"  - Max output tokens: {max_tokens}")
            print(f"  ⏰ Request time: {request_start.strftime('%H:%M:%S.%f')[:-3]}")
            
            response_text = call_vllm(prompt, **kwargs)
            
            elapsed_time = time.time() - start_time
            response_tokens = len(response_text.split())
            response_chars = len(response_text)
            
            print(f"✅ Response received from vLLM!")
            print(f"[LLM RESPONSE ← vLLM]")
            print(f"📤 OUTPUT:")
            print(f"  - Response length: {response_chars} chars, ~{response_tokens} tokens")
            print(f"  - Generation time: {elapsed_time:.2f}s")
            print(f"  - Speed: ~{response_tokens/elapsed_time:.1f} tokens/sec" if elapsed_time > 0 else "  - Speed: N/A")
            print(f"RESPONSE PREVIEW (first 500 chars):")
            print(f"{response_text[:500]}...")
            print(f"{'='*80}\n")
            
            return response_text
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"❌ vLLM ERROR after {elapsed_time:.3f}s: {e}")
            print(f"{'='*80}\n")
            return f"[vLLM ошибка: {e}]"
    
    return "[LLM выключена]"
