from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_OUTPUT_BLOCKED = (
    "I recommend consulting a doctor for proper medical advice."
)

# Dosage-like patterns (numbers + units, titration language)
_DOSAGE_RE = re.compile(
    r"\b\d{1,4}\s*(mg|mcg|g|ml|mL|IU|iu|units?)\b"
    r"|\b(take|taking)\s+\d+\s*(tablets?|pills?|caps?)\b"
    r"|\b\d+\s*mg/kg\b"
    r"|\b(increase|decrease|titrate)\s+(the\s+)?dose\b",
    re.I,
)

# Clinical prescribing language (avoid matching "can't prescribe" safety copy)
_PRESCRIBE_RE = re.compile(
    r"\b(I\s+will\s+prescribe|I\s+prescribe|I\s+am\s+prescribing|I'?m\s+prescribing|"
    r"start\s+you\s+on\s+\w+|put\s+you\s+on\s+\w+)\b",
    re.I,
)

# Short list of high-risk drug classes / common Rx names (not exhaustive)
_DRUG_HINT_RE = re.compile(
    r"\b(warfarin|metformin|lisinopril|atorvastatin|oxycodone|fentanyl|"
    r"benzodiazepine|Xanax|Adderall|amoxicillin|Zoloft|Prozac|"
    r"insulin\s+glargine|prednisone)\b",
    re.I,
)


def filter_output(response: str) -> str:
    """
    Post-LLM filter: block prescription/dosage-like advice.
    If triggered, replaces entire response with a safe disclaimer.
    """
    if not response or not response.strip():
        return response

    text = response
    if (
        _DOSAGE_RE.search(text)
        or _PRESCRIBE_RE.search(text)
        or _DRUG_HINT_RE.search(text)
    ):
        logger.warning("guardrails: output_filter redacted prescription/medical advice")
        return _OUTPUT_BLOCKED

    return text
