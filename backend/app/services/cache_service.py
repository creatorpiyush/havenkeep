import hashlib
import json
import time
from typing import Dict, Any, Optional

class ToolResultCache:
    """
    In-memory and TTL-based cache for deterministic, read-only tool invocation results.
    Prevents redundant tool calls across task cycles and sessions.
    """
    _cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def _make_key(cls, tool_name: str, kwargs: Dict[str, Any]) -> str:
        serialized = json.dumps(kwargs, sort_keys=True, default=str)
        hashed = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"{tool_name}:{hashed}"

    @classmethod
    def get(cls, tool_name: str, kwargs: Dict[str, Any]) -> Any:
        key = cls._make_key(tool_name, kwargs)
        entry = cls._cache.get(key)
        if not entry:
            return None
        
        # Check TTL expiration
        if time.time() > entry["expires_at"]:
            del cls._cache[key]
            return None
            
        return entry["result"]

    @classmethod
    def set(cls, tool_name: str, kwargs: Dict[str, Any], result: Any, ttl_seconds: int = 300) -> None:
        key = cls._make_key(tool_name, kwargs)
        cls._cache[key] = {
            "result": result,
            "expires_at": time.time() + ttl_seconds
        }

    @classmethod
    def clear(cls) -> None:
        cls._cache.clear()

    @classmethod
    def size(cls) -> int:
        return len(cls._cache)
