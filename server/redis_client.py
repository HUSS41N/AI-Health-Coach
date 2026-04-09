import hashlib
import json
import logging
import time
from functools import lru_cache

from upstash_redis import Redis

from config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_redis() -> Redis:
    s = get_settings()
    return Redis(url=s.upstash_redis_rest_url, token=s.upstash_redis_rest_token)


def check_redis() -> bool:
    try:
        get_redis().ping()
        return True
    except Exception:
        logger.exception("redis health check failed")
        return False


def _key(prefix: str, *parts: str) -> str:
    return f"coach:{prefix}:" + ":".join(parts)


def cache_messages_set(user_id: str, payload: list[dict]) -> None:
    try:
        get_redis().set(
            _key("msgs", user_id),
            json.dumps(payload),
            ex=get_settings().llm_cache_ttl_seconds,
        )
    except Exception:
        logger.debug("redis cache set failed", exc_info=True)


def cache_messages_get(user_id: str) -> list[dict] | None:
    try:
        raw = get_redis().get(_key("msgs", user_id))
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        logger.debug("redis cache get failed", exc_info=True)
        return None


def cache_messages_delete(user_id: str) -> None:
    try:
        get_redis().delete(_key("msgs", user_id))
    except Exception:
        logger.debug("redis cache delete failed", exc_info=True)


def llm_cache_get(cache_key: str) -> str | None:
    try:
        return get_redis().get(_key("llm", cache_key))
    except Exception:
        return None


def llm_cache_set(cache_key: str, value: str) -> None:
    try:
        get_redis().set(
            _key("llm", cache_key),
            value,
            ex=get_settings().llm_cache_ttl_seconds,
        )
    except Exception:
        pass


def rate_limit_allow(user_id: str) -> bool:
    settings = get_settings()
    key = _key("rl", user_id, str(int(time.time() // 60)))
    try:
        r = get_redis()
        n = int(r.incr(key))
        if n == 1:
            r.expire(key, 70)
        return n <= settings.rate_limit_per_minute
    except Exception:
        return True


def inflight_try_acquire(user_id: str, client_request_id: str) -> bool:
    if not client_request_id:
        return True
    key = _key("inflight", user_id, client_request_id)
    try:
        r = get_redis()
        ok = r.set(key, "1", nx=True, ex=120)
        return bool(ok)
    except Exception:
        return True


def inflight_release(user_id: str, client_request_id: str) -> None:
    if not client_request_id:
        return
    try:
        get_redis().delete(_key("inflight", user_id, client_request_id))
    except Exception:
        pass


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:48]


def _mem_ttl() -> int:
    return get_settings().memory_cache_ttl_seconds


def profile_cache_get(user_id: str) -> str | None:
    try:
        return get_redis().get(f"profile:{user_id}")
    except Exception:
        logger.debug("profile cache get failed", exc_info=True)
        return None


def profile_cache_set(user_id: str, json_payload: str) -> None:
    try:
        get_redis().set(f"profile:{user_id}", json_payload, ex=_mem_ttl())
    except Exception:
        logger.debug("profile cache set failed", exc_info=True)


def profile_cache_delete(user_id: str) -> None:
    try:
        get_redis().delete(f"profile:{user_id}")
    except Exception:
        logger.debug("profile cache delete failed", exc_info=True)


def summary_cache_get(user_id: str) -> str | None:
    try:
        raw = get_redis().get(f"summary:{user_id}")
        return raw
    except Exception:
        logger.debug("summary cache get failed", exc_info=True)
        return None


def summary_cache_set(user_id: str, text: str) -> None:
    try:
        get_redis().set(f"summary:{user_id}", text, ex=_mem_ttl())
    except Exception:
        logger.debug("summary cache set failed", exc_info=True)


def summary_cache_delete(user_id: str) -> None:
    try:
        get_redis().delete(f"summary:{user_id}")
    except Exception:
        logger.debug("summary cache delete failed", exc_info=True)


def _prompt_cache_key(key: str) -> str:
    return _key("aprompt", key)


def prompt_cache_get(prompt_key: str) -> str | None:
    try:
        return get_redis().get(_prompt_cache_key(prompt_key))
    except Exception:
        logger.debug("prompt cache get failed", exc_info=True)
        return None


def prompt_cache_set(prompt_key: str, value: str) -> None:
    try:
        get_redis().set(
            _prompt_cache_key(prompt_key),
            value,
            ex=min(600, get_settings().llm_cache_ttl_seconds * 2),
        )
    except Exception:
        logger.debug("prompt cache set failed", exc_info=True)


def prompt_cache_delete(prompt_key: str) -> None:
    try:
        get_redis().delete(_prompt_cache_key(prompt_key))
    except Exception:
        logger.debug("prompt cache delete failed", exc_info=True)
