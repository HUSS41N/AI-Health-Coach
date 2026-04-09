from __future__ import annotations

import logging
import time

from config import get_settings

logger = logging.getLogger(__name__)


def _window_key(user_id: str) -> str:
    """Fixed window per UTC minute; key pattern rate:{user_id}:{minute}."""
    minute = int(time.time() // 60)
    return f"rate:{user_id}:{minute}"


def check_rate_limit(user_id: str) -> bool:
    """
    Returns True if request is allowed, False if over limit.
    Uses Redis INCR with TTL; key family rate:{user_id}:{minute}.
    """
    settings = get_settings()
    limit = settings.guardrail_rate_limit_per_minute
    key = _window_key(user_id)
    try:
        from redis_client import get_redis

        r = get_redis()
        n = int(r.incr(key))
        if n == 1:
            r.expire(key, 70)
        ok = n <= limit
        if not ok:
            logger.warning(
                "guardrails: rate_limit exceeded user_id=%s count=%s limit=%s",
                user_id,
                n,
                limit,
            )
        return ok
    except Exception:
        logger.exception("guardrails: rate_limit check failed; allowing request")
        return True


def check_duplicate_message(user_id: str, content_hash: str, ttl_seconds: int = 45) -> bool:
    """
    Returns True if this submission is allowed, False if duplicate within TTL.
    """
    key = f"rate:dup:{user_id}:{content_hash}"
    try:
        from redis_client import get_redis

        r = get_redis()
        ok = r.set(key, "1", nx=True, ex=ttl_seconds)
        if not ok:
            logger.info("guardrails: duplicate message suppressed user_id=%s", user_id)
        return bool(ok)
    except Exception:
        return True
