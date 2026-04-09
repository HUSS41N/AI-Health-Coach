from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Public sentinel: compare sanitize_input() result to this to detect rejection.
INPUT_SANITIZE_REJECT = "Could you please rephrase your message?"

# Collapse 3+ repeated characters to one (e.g. heyyyy -> hey)
_REPEAT_RE = re.compile(r"(.)\1{2,}", re.DOTALL)

# Prompt-injection / role-break patterns (case-insensitive); replaced with neutral placeholder.
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|rules?|prompts?)",
        re.I,
    ),
    re.compile(r"disregard\s+(the\s+)?(above|previous)", re.I),
    re.compile(r"act\s+as\s+(a\s+)?doctor", re.I),
    re.compile(r"you\s+are\s+now\s+", re.I),
    re.compile(r"new\s+instructions?\s*:", re.I),
    re.compile(r"system\s+prompt\s*:", re.I),
    re.compile(r"override\s+(safety|rules?|instructions?)", re.I),
    re.compile(r"forget\s+(your\s+)?(rules?|instructions?|guidelines?)", re.I),
    re.compile(r"<\s*/?\s*system\s*>", re.I),
    re.compile(r"\[\s*INST\s*\]", re.I),
]


def _strip_garbage(s: str) -> str:
    """Keep printable text, newlines, tabs; drop other control characters."""
    out: list[str] = []
    for ch in s:
        if ch in "\n\t\r":
            out.append("\n" if ch == "\r" else ch)
            continue
        cat = unicodedata.category(ch)
        if cat.startswith("C") and ch not in "\n\t":
            continue
        if ch.isprintable():
            out.append(ch)
    return "".join(out)


def _normalize_repeats(s: str) -> str:
    return _REPEAT_RE.sub(r"\1", s)


def sanitize_input(message: str, *, max_length: int = 2000) -> str:
    """
    Trim, strip unsafe control chars, cap length, normalize repeats.
    If invalid (empty after processing), returns INPUT_SANITIZE_REJECT.
    """
    if message is None:
        logger.info("guardrails: invalid input (null)")
        return INPUT_SANITIZE_REJECT

    raw = message.strip()
    if not raw:
        logger.info("guardrails: invalid input (empty)")
        return INPUT_SANITIZE_REJECT

    cleaned = _strip_garbage(raw)
    cleaned = cleaned.strip()
    if not cleaned:
        logger.info("guardrails: invalid input (no printable content)")
        return INPUT_SANITIZE_REJECT

    cleaned = _normalize_repeats(cleaned)
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip()
        logger.debug("guardrails: input truncated to %s chars", max_length)

    return cleaned


@dataclass(frozen=True, slots=True)
class PreparedUserMessage:
    """Result of server-side input preparation before persistence / LLM."""

    rejected: bool
    storage_text: str
    pipeline_text: str
    immediate_assistant: str | None


def prepare_user_message(message: str, *, max_length: int = 2000) -> PreparedUserMessage:
    """
    Validate and scrub user text. If rejected, `immediate_assistant` carries the
    canned reply and `storage_text` holds a short audit snippet (may be empty).
    """
    s = sanitize_input(message, max_length=max_length)
    if s == INPUT_SANITIZE_REJECT:
        audit = (message or "").strip()
        audit = _strip_garbage(audit)[:500] if audit else ""
        storage = audit or "(empty)"
        logger.info("guardrails: user message rejected after sanitization")
        return PreparedUserMessage(
            rejected=True,
            storage_text=storage,
            pipeline_text="",
            immediate_assistant=INPUT_SANITIZE_REJECT,
        )
    scrubbed = sanitize_prompt(s)
    return PreparedUserMessage(
        rejected=False,
        storage_text=scrubbed,
        pipeline_text=scrubbed,
        immediate_assistant=None,
    )


def sanitize_prompt(user_message: str) -> str:
    """
    Reduce prompt-injection surface before text is stored or sent to the LLM.
    System prompts remain authoritative; user content is scrubbed in-place.
    """
    if not user_message:
        return user_message
    text = user_message
    for pat in _INJECTION_PATTERNS:
        text = pat.sub("[removed]", text)
    return text.strip()
