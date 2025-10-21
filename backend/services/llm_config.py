"""
LLM Model Configuration Registry
Centralized configuration for different LLM models with their capabilities
"""

import os
from typing import Dict, Optional
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass
class LLMModelConfig:
    """Configuration for a specific LLM model"""
    
    # Model identification
    model_name: str
    provider: str  # ollama, vllm, openai, etc.
    
    # Context window
    context_window: int  # Total context window size
    max_output_tokens: int  # Maximum tokens in response
    
    # Summarization settings (derived from context window)
    summarization_threshold: int  # When to trigger auto-summarization
    summarization_max_output: int  # Max tokens in summary
    
    # Performance characteristics
    tokens_per_second: int  # Approximate throughput
    supports_streaming: bool = True
    supports_function_calling: bool = False
    
    # Cost (if applicable)
    cost_per_1k_input_tokens: float = 0.0  # For cloud models
    cost_per_1k_output_tokens: float = 0.0
    
    # Additional metadata
    description: str = ""
    recommended_use_cases: list = None
    
    def __post_init__(self):
        if self.recommended_use_cases is None:
            self.recommended_use_cases = []
    
    @property
    def effective_context_for_rag(self) -> int:
        """
        Effective context size for RAG (accounting for prompt + output)
        Formula: context_window - max_output_tokens - system_prompt_overhead
        """
        system_overhead = 500  # Примерно для system prompt
        return self.context_window - self.max_output_tokens - system_overhead
    
    @property
    def recommended_chunk_limit(self) -> int:
        """
        Recommended number of chunks based on context window
        Assumes ~300 tokens per chunk average
        """
        avg_tokens_per_chunk = 300
        return max(1, int(self.effective_context_for_rag / avg_tokens_per_chunk))


class LLMModelRegistry:
    """Registry of LLM model configurations"""
    
    def __init__(self):
        self._models: Dict[str, LLMModelConfig] = {}
        self._load_default_models()
    
    def _load_default_models(self):
        """Load default model configurations"""
        
        # ===== OLLAMA MODELS =====
        
        self.register(LLMModelConfig(
            model_name="llama3.1:8b",
            provider="ollama",
            context_window=8192,
            max_output_tokens=512,
            summarization_threshold=3000,  # ~40% of effective context
            summarization_max_output=1500,
            tokens_per_second=50,
            supports_streaming=True,
            supports_function_calling=False,
            description="Llama 3.1 8B - balanced performance",
            recommended_use_cases=["general", "chat", "rag"]
        ))
        
        self.register(LLMModelConfig(
            model_name="llama3.1:70b",
            provider="ollama",
            context_window=8192,
            max_output_tokens=512,
            summarization_threshold=3000,
            summarization_max_output=1500,
            tokens_per_second=15,
            supports_streaming=True,
            supports_function_calling=False,
            description="Llama 3.1 70B - high quality",
            recommended_use_cases=["complex_reasoning", "analysis"]
        ))
        
        self.register(LLMModelConfig(
            model_name="mistral:7b",
            provider="ollama",
            context_window=8192,
            max_output_tokens=512,
            summarization_threshold=3000,
            summarization_max_output=1500,
            tokens_per_second=60,
            supports_streaming=True,
            description="Mistral 7B - fast and efficient"
        ))
        
        # ===== vLLM MODELS =====
        
        self.register(LLMModelConfig(
            model_name="meta-llama/Meta-Llama-3.1-8B-Instruct",
            provider="vllm",
            context_window=8192,
            max_output_tokens=512,
            summarization_threshold=3000,
            summarization_max_output=1500,
            tokens_per_second=250,  # Much faster with vLLM
            supports_streaming=True,
            supports_function_calling=True,
            description="Llama 3.1 8B via vLLM - optimized for GPU"
        ))
        
        self.register(LLMModelConfig(
            model_name="neuralmagic/Meta-Llama-3.1-70B-Instruct-FP8",
            provider="vllm",
            context_window=16384,  # Blackwell allows larger context
            max_output_tokens=1024,
            summarization_threshold=6000,  # ~40% of effective context
            summarization_max_output=3000,
            tokens_per_second=200,
            supports_streaming=True,
            supports_function_calling=True,
            description="Llama 3.1 70B FP8 - large context on Blackwell"
        ))
        
        self.register(LLMModelConfig(
            model_name="mistralai/Mixtral-8x7B-Instruct-v0.1",
            provider="vllm",
            context_window=32768,  # Large context window
            max_output_tokens=1024,
            summarization_threshold=12000,  # Can handle more before summarizing
            summarization_max_output=4000,
            tokens_per_second=180,
            supports_streaming=True,
            description="Mixtral 8x7B - very large context"
        ))
        
        # ===== CLOUD MODELS (for reference) =====
        
        self.register(LLMModelConfig(
            model_name="gpt-4",
            provider="openai",
            context_window=8192,
            max_output_tokens=1024,
            summarization_threshold=3000,
            summarization_max_output=1500,
            tokens_per_second=40,
            supports_streaming=True,
            supports_function_calling=True,
            cost_per_1k_input_tokens=0.03,
            cost_per_1k_output_tokens=0.06,
            description="GPT-4 - highest quality"
        ))
        
        self.register(LLMModelConfig(
            model_name="gpt-4-turbo",
            provider="openai",
            context_window=128000,  # Very large context
            max_output_tokens=4096,
            summarization_threshold=50000,  # Can handle huge contexts
            summarization_max_output=10000,
            tokens_per_second=100,
            supports_streaming=True,
            supports_function_calling=True,
            cost_per_1k_input_tokens=0.01,
            cost_per_1k_output_tokens=0.03,
            description="GPT-4 Turbo - large context, faster"
        ))
        
        self.register(LLMModelConfig(
            model_name="claude-3-sonnet",
            provider="anthropic",
            context_window=200000,  # Huge context
            max_output_tokens=4096,
            summarization_threshold=80000,
            summarization_max_output=15000,
            tokens_per_second=80,
            supports_streaming=True,
            supports_function_calling=True,
            cost_per_1k_input_tokens=0.003,
            cost_per_1k_output_tokens=0.015,
            description="Claude 3 Sonnet - massive context"
        ))
    
    def register(self, model_config: LLMModelConfig):
        """Register a model configuration"""
        key = self._make_key(model_config.provider, model_config.model_name)
        self._models[key] = model_config
    
    def get(self, provider: str, model_name: str) -> Optional[LLMModelConfig]:
        """Get model configuration"""
        key = self._make_key(provider, model_name)
        return self._models.get(key)
    
    def get_or_default(self, provider: str, model_name: str) -> LLMModelConfig:
        """
        Get model configuration or return sensible defaults
        """
        config = self.get(provider, model_name)
        
        if config:
            return config
        
        # Return conservative defaults for unknown models
        print(f"[LLMConfig] Unknown model {provider}:{model_name}, using defaults")
        return LLMModelConfig(
            model_name=model_name,
            provider=provider,
            context_window=8192,  # Conservative default
            max_output_tokens=512,
            summarization_threshold=3000,
            summarization_max_output=1500,
            tokens_per_second=50,
            description=f"Unknown model (using defaults)"
        )
    
    def list_models(self, provider: Optional[str] = None) -> list[LLMModelConfig]:
        """List all registered models, optionally filtered by provider"""
        models = list(self._models.values())
        if provider:
            models = [m for m in models if m.provider == provider]
        return models
    
    def _make_key(self, provider: str, model_name: str) -> str:
        """Create unique key for model"""
        return f"{provider}::{model_name}"
    
    def load_from_file(self, config_path: Path):
        """Load model configurations from JSON file"""
        if not config_path.exists():
            return
        
        with open(config_path, 'r') as f:
            data = json.load(f)
        
        for model_data in data.get('models', []):
            config = LLMModelConfig(**model_data)
            self.register(config)
    
    def export_to_file(self, output_path: Path):
        """Export configurations to JSON file"""
        models_data = []
        for model in self._models.values():
            models_data.append({
                'model_name': model.model_name,
                'provider': model.provider,
                'context_window': model.context_window,
                'max_output_tokens': model.max_output_tokens,
                'summarization_threshold': model.summarization_threshold,
                'summarization_max_output': model.summarization_max_output,
                'tokens_per_second': model.tokens_per_second,
                'supports_streaming': model.supports_streaming,
                'supports_function_calling': model.supports_function_calling,
                'description': model.description,
                'recommended_use_cases': model.recommended_use_cases,
            })
        
        with open(output_path, 'w') as f:
            json.dump({'models': models_data}, f, indent=2)


# Global registry (singleton)
_global_registry: Optional[LLMModelRegistry] = None


def get_llm_registry(config_path: Optional[Path] = None) -> LLMModelRegistry:
    """Get global LLM model registry"""
    global _global_registry
    if _global_registry is None:
        _global_registry = LLMModelRegistry()
        
        # Load custom configs if provided
        if config_path and config_path.exists():
            _global_registry.load_from_file(config_path)
    
    return _global_registry


def get_current_model_config() -> LLMModelConfig:
    """
    Get configuration for currently active LLM model
    Reads from environment variables LLM_MODE and LLM_MODEL
    """
    from . import config
    
    registry = get_llm_registry()
    return registry.get_or_default(config.LLM_MODE, config.LLM_MODEL)

