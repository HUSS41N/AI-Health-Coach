import logging

from agents.schemas import IntentOutput
from llm.client import complete_json_chat
from prompts.service import get_prompt_content

logger = logging.getLogger(__name__)


def run_intent_agent(user_message: str) -> IntentOutput:
    try:
        system = get_prompt_content("intent_classifier")
        data, provider = complete_json_chat(
            system,
            f'User message:\n"""{user_message}"""',
        )
        out = IntentOutput.model_validate(data)
        logger.debug("intent agent (%s): %s", provider, out.model_dump())
        return out
    except Exception as e:
        logger.warning("intent agent failed, using default: %s", e)
        return IntentOutput(
            intent="health_query",
            entities=[],
            urgency="low",
        )
