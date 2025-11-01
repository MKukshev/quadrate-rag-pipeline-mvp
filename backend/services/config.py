
import os
from pathlib import Path

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "docs")
QDRANT_HNSW_M = int(os.getenv("QDRANT_HNSW_M", "16"))
QDRANT_HNSW_EF_CONSTRUCT = int(os.getenv("QDRANT_HNSW_EF_CONSTRUCT", "100"))
QDRANT_HNSW_EF_SEARCH = int(os.getenv("QDRANT_HNSW_EF_SEARCH", "64"))

EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

KEYWORD_INDEX_DIR = Path(os.getenv("KEYWORD_INDEX_DIR", "/data/whoosh_index")).resolve()
KEYWORD_INDEX_DIR.mkdir(parents=True, exist_ok=True)

LLM_MODE = os.getenv("LLM_MODE", "ollama")     # ollama|vllm|none
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
LLM_VLLM_URL = os.getenv("LLM_VLLM_URL", "http://vllm:8001/v1")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))

_DEFAULT_DOC_TYPE_MODEL_PATH = (
    Path(__file__).resolve().parents[1] / "models" / "doc_type_classifier.joblib"
)
_DOC_TYPE_MODEL_ENV = os.getenv("DOC_TYPE_MODEL_PATH")
DOC_TYPE_MODEL_PATH = (
    Path(_DOC_TYPE_MODEL_ENV).expanduser().resolve()
    if _DOC_TYPE_MODEL_ENV
    else _DEFAULT_DOC_TYPE_MODEL_PATH
)

AUTO_DOC_TYPES = os.getenv("AUTO_DOC_TYPES", "true").lower() == "true"

LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "240"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "256"))
LLM_STREAM_ENABLED = os.getenv("LLM_STREAM_ENABLED", "false").lower() == "true"

# Ollama specific config
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))  # Context window size for Ollama

CHUNK_TOKENS = int(os.getenv("CHUNK_TOKENS", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
CONTEXT_MAX_CHUNKS = int(os.getenv("CONTEXT_MAX_CHUNKS", "6"))
ONE_CHUNK_PER_DOC = os.getenv("ONE_CHUNK_PER_DOC", "true").lower() == "true"
CONTEXT_SNIPPET_MAX_CHARS = int(os.getenv("CONTEXT_SNIPPET_MAX_CHARS", "600"))
TOP_K_DEFAULT = int(os.getenv("TOP_K_DEFAULT", "6"))
TOP_K_MIN = int(os.getenv("TOP_K_MIN", "4"))
TOP_K_MAX = int(os.getenv("TOP_K_MAX", "8"))

ALLOWED_EXT = {".txt", ".md", ".pdf", ".docx", ".xlsx", ".csv"}

MMR_ENABLED = os.getenv("MMR_ENABLED", "true").lower() == "true"
MMR_LAMBDA = float(os.getenv("MMR_LAMBDA", "0.7"))
MMR_CANDIDATE_MULTIPLIER = int(os.getenv("MMR_CANDIDATE_MULTIPLIER", "3"))

CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))
CACHE_MAX_ITEMS = int(os.getenv("CACHE_MAX_ITEMS", "256"))

RERANK_ENABLED = os.getenv("RERANK_ENABLED", "false").lower() == "true"
RERANK_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RERANK_MAX_CANDIDATES = int(os.getenv("RERANK_MAX_CANDIDATES", "32"))
RERANK_BATCH_SIZE = int(os.getenv("RERANK_BATCH_SIZE", "16"))
