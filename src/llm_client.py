import json
import re
from typing import Any, Type
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from src.config import (
    GEMINI_MODEL,
    GOOGLE_API_KEY,
    GROQ_API_KEY,
    GROQ_MODEL
)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def gemini_model() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=0,
        client_options={"api_endpoint": "generativelanguage.googleapis.com"},
    )

def groq_model() -> ChatGroq:
    return ChatGroq(
        model=GROQ_MODEL,
        groq_api_key=GROQ_API_KEY,
        temperature=0,
    )


def _extract_json_block(text: str) -> str:
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    match = re.search(r"\{[\s\S]*\}", text)
    return match.group(0) if match else "{}"

def _messages(system_prompt: str, user_prompt: str) -> list:
    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]


def invoke_structured(
    system_prompt: str,
    user_prompt: str,
    schema: Type[BaseModel],
) -> tuple[BaseModel, str]:
    errors: list[str] = []
    result = None
    provider = ""

    if GOOGLE_API_KEY.strip():
        try:
            result = gemini_model().with_structured_output(schema).invoke(_messages(system_prompt, user_prompt))
            provider = "gemini"
        except Exception as exc:
            logger.error(f"gemini failed: {exc}")

    if result is None and GROQ_API_KEY.strip():
        try:
            result = groq_model().with_structured_output(schema).invoke(_messages(system_prompt, user_prompt))
            provider = "groq"
        except Exception as exc:
            logger.error(f"groq failed: {exc}")

    if result is None:
        detail = " | ".join(errors) if errors else "No API keys configured."
        logger.error(f"No working LLM backend for structured output. {detail}")
        raise RuntimeError(f"No working LLM backend for structured output. {detail}")
    
    if isinstance(result, schema):
        return result, provider
    if isinstance(result, dict):
        return schema.model_validate(result), provider
    return schema.model_validate_json(str(result)), provider


def invoke_json(system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], str]:
    if GOOGLE_API_KEY.strip():
        try:
            output = str(gemini_model().invoke(_messages(system_prompt, user_prompt)).content)
            return json.loads(_extract_json_block(output)), "gemini"
        except Exception as exc:
            logger.error(f"gemini failed: {exc}")

    if GROQ_API_KEY.strip():
        try:
            output = str(groq_model().invoke(_messages(system_prompt, user_prompt)).content)
            return json.loads(_extract_json_block(output)), "groq"
        except Exception as exc:
            logger.error(f"groq failed: {exc}")

    logger.error("No working LLM backend for json. Ensure GOOGLE_API_KEY and/or GROQ_API_KEY are set.")
    raise RuntimeError("No working LLM backend for json. Ensure GOOGLE_API_KEY and/or GROQ_API_KEY are set.")
