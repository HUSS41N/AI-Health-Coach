"""Guardrails-specific errors (optional typing / handling)."""


class GuardrailsError(Exception):
    """Base class for guardrail pipeline errors."""


class LLMProviderExhausted(GuardrailsError):
    """All LLM providers and retries failed."""


class InvalidUserInput(GuardrailsError):
    """User input failed sanitization."""
