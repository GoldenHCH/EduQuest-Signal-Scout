"""LLM provider abstraction for Utah Board Signal Scout."""

import json
from pathlib import Path

from langchain_openai import ChatOpenAI
from loguru import logger
from openai import OpenAI

from src.config import settings


def get_llm(
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 2048,
) -> ChatOpenAI:
    """Get an LLM instance.

    Args:
        model: Model name. Defaults to settings.openai_model.
        temperature: Sampling temperature (0-1). Lower = more deterministic.
        max_tokens: Maximum tokens in response.

    Returns:
        ChatOpenAI instance configured for use.

    Raises:
        ValueError: If no API key is configured.
    """
    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY not set. Please set it in your .env file or environment."
        )

    model = model or settings.openai_model

    logger.debug(f"Creating LLM instance: model={model}, temperature={temperature}")

    return ChatOpenAI(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=settings.openai_api_key,
    )


def _extract_json_from_response(content: str) -> str:
    """Extract JSON from LLM response, handling markdown fences.

    Args:
        content: Raw response content from LLM.

    Returns:
        Cleaned JSON string.
    """
    # Handle case where LLM wraps JSON in markdown code blocks
    if "```json" in content:
        start = content.find("```json") + 7
        end = content.find("```", start)
        content = content[start:end].strip()
    elif "```" in content:
        start = content.find("```") + 3
        end = content.find("```", start)
        content = content[start:end].strip()
    return content.strip()


def invoke_llm_json(prompt: str, model: str | None = None) -> dict:
    """Invoke LLM and parse JSON response.

    Args:
        prompt: The prompt to send to the LLM.
        model: Optional model override.

    Returns:
        Parsed JSON response as a dictionary.

    Raises:
        ValueError: If response is not valid JSON.
    """
    llm = get_llm(model=model)
    response = llm.invoke(prompt)
    content = _extract_json_from_response(response.content)

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {content[:200]}")
        raise ValueError(f"LLM response is not valid JSON: {e}") from e


def invoke_llm_json_any(prompt: str, model: str | None = None) -> dict | list:
    """Invoke LLM and parse JSON response (dict or list).

    Args:
        prompt: The prompt to send to the LLM.
        model: Optional model override.

    Returns:
        Parsed JSON response as a dictionary or list.

    Raises:
        ValueError: If response is not valid JSON.
    """
    llm = get_llm(model=model)
    response = llm.invoke(prompt)
    content = _extract_json_from_response(response.content)

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {content[:200]}")
        raise ValueError(f"LLM response is not valid JSON: {e}") from e


def invoke_llm_with_pdf(
    pdf_path: Path,
    prompt: str,
    model: str | None = None,
) -> dict | list:
    """Invoke LLM with a PDF file attachment using OpenAI Files API.

    This function uploads the PDF to OpenAI's Files API, then calls the model
    with the file_id attached. This avoids holding base64-expanded content in memory.

    Args:
        pdf_path: Path to the PDF file to analyze.
        prompt: The prompt/instructions for analyzing the PDF.
        model: Optional model override. Defaults to settings.openai_model.

    Returns:
        Parsed JSON response (expected to be a list of signals).

    Raises:
        ValueError: If no API key is configured or response is not valid JSON.
        FileNotFoundError: If the PDF file doesn't exist.
    """
    if not settings.openai_api_key:
        raise ValueError(
            "OPENAI_API_KEY not set. Please set it in your .env file or environment."
        )

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    model = model or settings.openai_model
    client = OpenAI(api_key=settings.openai_api_key)

    logger.debug(f"Uploading PDF to OpenAI: {pdf_path.name}")

    # Upload the PDF file
    with open(pdf_path, "rb") as f:
        uploaded_file = client.files.create(file=f, purpose="assistants")

    logger.debug(f"Uploaded file_id: {uploaded_file.id}")

    try:
        # Call the model with the file attachment
        logger.debug(f"Calling model {model} with PDF attachment")
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_file",
                            "file_id": uploaded_file.id,
                        },
                        {
                            "type": "input_text",
                            "text": prompt,
                        },
                    ],
                }
            ],
            temperature=0.1,
        )

        # Extract the text content from response
        content = response.output_text
        logger.debug(f"Received response: {len(content)} chars")

        # Parse JSON from response
        content = _extract_json_from_response(content)
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {content[:500]}")
            raise ValueError(f"LLM response is not valid JSON: {e}") from e

    finally:
        # Clean up: delete the uploaded file
        try:
            client.files.delete(uploaded_file.id)
            logger.debug(f"Deleted uploaded file: {uploaded_file.id}")
        except Exception as e:
            logger.warning(f"Failed to delete uploaded file {uploaded_file.id}: {e}")
