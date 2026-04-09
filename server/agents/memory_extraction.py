import logging

from agents.schemas import MemoryExtractionOutput
from llm.client import complete_json_chat
from prompts.service import get_prompt_content

logger = logging.getLogger(__name__)


def run_memory_extraction_agent(user_message: str) -> MemoryExtractionOutput:
    try:
        system = get_prompt_content("memory_extraction")
        data, provider = complete_json_chat(
            system,
            f'User message:\n"""{user_message}"""',
        )
        out = MemoryExtractionOutput.model_validate(data)
        logger.debug("memory extraction (%s): %s", provider, out.model_dump())
        return out
    except Exception as e:
        logger.warning("memory extraction failed: %s", e)
        return MemoryExtractionOutput(update_profile=None, store_memory=[])
