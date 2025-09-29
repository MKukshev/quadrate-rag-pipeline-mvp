import time
from threading import Lock
from typing import Dict

class _Metrics:
    def __init__(self):
        self._lock = Lock()
        self._reset()

    def _reset(self):
        self.search_requests = 0
        self.search_latency_ms = 0.0
        self.search_context_tokens = 0
        self.search_cache_hits = 0

        self.ask_requests = 0
        self.ask_latency_ms = 0.0
        self.ask_context_tokens = 0
        self.ask_answer_tokens = 0
        self.ask_cache_hits = 0

    def record_search(self, latency_ms: float, context_tokens: int, cache_hit: bool):
        with self._lock:
            self.search_requests += 1
            self.search_latency_ms += latency_ms
            self.search_context_tokens += context_tokens
            if cache_hit:
                self.search_cache_hits += 1

    def record_ask(self, latency_ms: float, context_tokens: int, answer_tokens: int, cache_hit: bool):
        with self._lock:
            self.ask_requests += 1
            self.ask_latency_ms += latency_ms
            self.ask_context_tokens += context_tokens
            self.ask_answer_tokens += answer_tokens
            if cache_hit:
                self.ask_cache_hits += 1

    def snapshot(self) -> Dict:
        with self._lock:
            search_avg_latency = (self.search_latency_ms / self.search_requests) if self.search_requests else 0.0
            search_avg_context = (self.search_context_tokens / self.search_requests) if self.search_requests else 0.0
            search_cache_rate = (self.search_cache_hits / self.search_requests) if self.search_requests else 0.0

            ask_avg_latency = (self.ask_latency_ms / self.ask_requests) if self.ask_requests else 0.0
            ask_avg_context = (self.ask_context_tokens / self.ask_requests) if self.ask_requests else 0.0
            ask_avg_answer = (self.ask_answer_tokens / self.ask_requests) if self.ask_requests else 0.0
            ask_cache_rate = (self.ask_cache_hits / self.ask_requests) if self.ask_requests else 0.0

            return {
                "timestamp": time.time(),
                "search": {
                    "requests": self.search_requests,
                    "avg_latency_ms": round(search_avg_latency, 2),
                    "avg_context_tokens": round(search_avg_context, 2),
                    "cache_hit_rate": round(search_cache_rate, 3),
                },
                "ask": {
                    "requests": self.ask_requests,
                    "avg_latency_ms": round(ask_avg_latency, 2),
                    "avg_context_tokens": round(ask_avg_context, 2),
                    "avg_answer_tokens": round(ask_avg_answer, 2),
                    "cache_hit_rate": round(ask_cache_rate, 3),
                },
            }

_metrics = _Metrics()


def record_search(latency_ms: float, context_tokens: int, cache_hit: bool):
    _metrics.record_search(latency_ms, context_tokens, cache_hit)


def record_ask(latency_ms: float, context_tokens: int, answer_tokens: int, cache_hit: bool):
    _metrics.record_ask(latency_ms, context_tokens, answer_tokens, cache_hit)


def snapshot() -> Dict:
    return _metrics.snapshot()
