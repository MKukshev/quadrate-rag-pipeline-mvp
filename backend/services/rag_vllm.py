"""
RAG module with vLLM support
Extends rag.py to support vLLM OpenAI-compatible API
"""

import os
import requests
from typing import List, Dict, Optional
from . import config

# vLLM configuration
VLLM_URL = os.getenv("LLM_VLLM_URL", "http://vllm:8001/v1")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "dummy")  # vLLM doesn't require real key


def call_vllm(prompt: str, model: Optional[str] = None, **kwargs) -> str:
    """
    Call vLLM using OpenAI-compatible API
    
    Args:
        prompt: The prompt to send to the model
        model: Model name (optional, uses LLM_MODEL from config)
        **kwargs: Additional parameters (temperature, max_tokens, etc.)
    
    Returns:
        Generated text response
    """
    model = model or config.LLM_MODEL
    
    # vLLM OpenAI-compatible endpoint
    url = f"{VLLM_URL}/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {VLLM_API_KEY}"
    }
    
    # Prepare request
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": kwargs.get("max_tokens", config.LLM_MAX_TOKENS),
        "temperature": kwargs.get("temperature", getattr(config, "LLM_TEMPERATURE", 0.7)),
        "stream": kwargs.get("stream", False),
    }
    
    # Add optional parameters
    if "top_p" in kwargs:
        payload["top_p"] = kwargs["top_p"]
    if "frequency_penalty" in kwargs:
        payload["frequency_penalty"] = kwargs["frequency_penalty"]
    if "presence_penalty" in kwargs:
        payload["presence_penalty"] = kwargs["presence_penalty"]
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=config.LLM_TIMEOUT
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Extract answer from OpenAI-compatible response
        if "choices" in result and len(result["choices"]) > 0:
            message = result["choices"][0].get("message", {})
            content = message.get("content", "")
            return content.strip()
        
        return "[vLLM error: unexpected response format]"
    
    except requests.exceptions.Timeout:
        return f"[vLLM error: timeout after {config.LLM_TIMEOUT}s]"
    except requests.exceptions.RequestException as e:
        return f"[vLLM error: {str(e)}]"
    except Exception as e:
        return f"[vLLM error: {str(e)}]"


def call_vllm_streaming(prompt: str, model: Optional[str] = None, **kwargs):
    """
    Call vLLM with streaming support
    
    Args:
        prompt: The prompt to send
        model: Model name
        **kwargs: Additional parameters
        
    Yields:
        Text chunks as they arrive
    """
    model = model or config.LLM_MODEL
    
    url = f"{VLLM_URL}/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {VLLM_API_KEY}"
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": kwargs.get("max_tokens", config.LLM_MAX_TOKENS),
        "temperature": kwargs.get("temperature", getattr(config, "LLM_TEMPERATURE", 0.7)),
        "stream": True,
    }
    
    try:
        with requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=config.LLM_TIMEOUT,
            stream=True
        ) as response:
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]  # Remove 'data: ' prefix
                        if data_str == '[DONE]':
                            break
                        
                        try:
                            import json
                            data = json.loads(data_str)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
    
    except Exception as e:
        yield f"[vLLM streaming error: {str(e)}]"


def check_vllm_health() -> tuple[bool, str]:
    """
    Check if vLLM service is available and healthy
    
    Returns:
        (is_healthy, detail_message)
    """
    try:
        response = requests.get(
            f"{VLLM_URL}/health",
            timeout=5
        )
        response.raise_for_status()
        return True, "vLLM is healthy"
    except requests.exceptions.ConnectionError:
        return False, f"Cannot connect to vLLM at {VLLM_URL}"
    except requests.exceptions.Timeout:
        return False, "vLLM health check timeout"
    except Exception as e:
        return False, f"vLLM health check failed: {str(e)}"


def get_vllm_models() -> List[str]:
    """
    Get list of available models from vLLM
    
    Returns:
        List of model names
    """
    try:
        response = requests.get(
            f"{VLLM_URL}/models",
            headers={"Authorization": f"Bearer {VLLM_API_KEY}"},
            timeout=5
        )
        response.raise_for_status()
        result = response.json()
        
        if "data" in result:
            return [model["id"] for model in result["data"]]
        return []
    
    except Exception:
        return []

