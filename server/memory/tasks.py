from __future__ import annotations

import logging

from db.session import get_session_factory
from memory.episodic import store_episodic_memory
from memory.long_term import apply_long_term_from_message
from memory.retrieval import invalidate_user_memory_caches
from memory.summary import maybe_refresh_summary_for_user

logger = logging.getLogger(__name__)


def run_post_chat_memory_work(
    user_id: str,
    user_message: str,
    assistant_message: str,
) -> None:
    """Background: profile merge, episodic store, rolling summary."""
    _ = assistant_message  # reserved for future (e.g. dyad extraction)
    if not (user_message or "").strip():
        return
    factory = get_session_factory()
    session = factory()
    try:
        apply_long_term_from_message(session, user_id, user_message)
        store_episodic_memory(session, user_id, user_message)
        maybe_refresh_summary_for_user(session, user_id)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("post-chat memory work failed for user %s", user_id)
    finally:
        session.close()
        invalidate_user_memory_caches(user_id)
