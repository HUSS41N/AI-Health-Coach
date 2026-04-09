import logging
import re

from agents.schemas import (
    ChoiceItem,
    IntentOutput,
    QuestionAgentOutput,
    ScaleConfig,
)
from llm.client import complete_json_chat
from protocol.engine import ProtocolOutput
from prompts.service import get_prompt_content

logger = logging.getLogger(__name__)

_ANXIETY = re.compile(
    r"\b(anxiety|anxious|panic|worried|worry|nervous|stress|stressed)\b",
    re.I,
)
_FEVER = re.compile(
    r"\b(fever|temperature|febrile|chills|feeling\s+hot)\b",
    re.I,
)


def _anxiety_scale() -> QuestionAgentOutput:
    return QuestionAgentOutput(
        interaction="scale",
        prompt="How intense does this feel right now? (0 = calm, 10 = overwhelming)",
        scale=ScaleConfig(
            id="anxiety_intensity",
            min=0,
            max=10,
            step=1,
            label_low="Calm / none",
            label_high="Overwhelming",
            title="Anxiety level",
        ),
        choices=[],
    )


def _fever_scale() -> QuestionAgentOutput:
    return QuestionAgentOutput(
        interaction="scale",
        prompt="How unwell does the fever or temperature feel to you right now?",
        scale=ScaleConfig(
            id="fever_severity",
            min=0,
            max=10,
            step=1,
            label_low="Mild",
            label_high="Very severe",
            title="Fever / unwell level",
        ),
        choices=[],
    )


def _llm_choices(user_message: str, intent: IntentOutput) -> QuestionAgentOutput:
    system = get_prompt_content("question_choices_llm")

    user = f"User message:\n{user_message}\nIntent: {intent.intent}\nEntities: {intent.entities}"
    try:
        data, _ = complete_json_chat(system, user)
        raw_choices = data.get("choices") or []
        cleaned: list[ChoiceItem] = []
        for i, c in enumerate(raw_choices[:4]):
            if not isinstance(c, dict):
                continue
            lab = str(c.get("label", "")).strip()
            if not lab:
                continue
            cid = str(c.get("id") or f"opt{i}").strip()[:32]
            cleaned.append(ChoiceItem(id=cid or f"opt{i}", label=lab[:80]))
        inter = str(data.get("interaction") or "none")
        if inter != "choices" or not cleaned:
            return QuestionAgentOutput()
        return QuestionAgentOutput(
            interaction="choices",
            prompt=str(data.get("prompt") or "Quick reply:")[:300],
            choices=cleaned,
            scale=None,
        )
    except Exception as e:
        logger.warning("question LLM failed: %s", e)
        return QuestionAgentOutput()


def run_question_agent(
    user_message: str,
    intent: IntentOutput,
    protocol: ProtocolOutput,
) -> QuestionAgentOutput:
    if intent.intent == "emergency" or protocol.protocol == "emergency":
        return QuestionAgentOutput()

    text = user_message.strip()
    if _ANXIETY.search(text):
        return _anxiety_scale()
    if _FEVER.search(text):
        return _fever_scale()

    if intent.intent in ("health_query", "onboarding"):
        return _llm_choices(text, intent)

    return QuestionAgentOutput()
