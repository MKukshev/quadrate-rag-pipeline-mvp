import time
from collections import OrderedDict
from threading import Lock
from typing import Any, Hashable, Optional

from . import config


class TTLCache:
    def __init__(self, maxsize: int, ttl: int):
        self.maxsize = maxsize
        self.ttl = ttl
        self._data: OrderedDict[Hashable, tuple[Any, float]] = OrderedDict()
        self._lock = Lock()

    def _purge(self) -> None:
        if not self._data:
            return
        now = time.time()
        keys_to_delete = [key for key, (_, ts) in self._data.items() if now - ts > self.ttl]
        for key in keys_to_delete:
            self._data.pop(key, None)

    def get(self, key: Hashable) -> Optional[Any]:
        with self._lock:
            self._purge()
            if key not in self._data:
                return None
            value, timestamp = self._data.pop(key)
            self._data[key] = (value, timestamp)
            return value

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._purge()
            if key in self._data:
                self._data.pop(key)
            self._data[key] = (value, time.time())
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


search_cache = TTLCache(config.CACHE_MAX_ITEMS, config.CACHE_TTL_SECONDS)
ask_cache = TTLCache(config.CACHE_MAX_ITEMS, config.CACHE_TTL_SECONDS)
