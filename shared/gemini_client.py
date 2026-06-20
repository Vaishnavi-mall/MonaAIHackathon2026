"""
shared/gemini_client.py
-----------------------
Single Gemini client used by all 10 agents.
Model name and defaults live here — change once, affects everything.

Naming: snake_case functions, PascalCase class, UPPER_SNAKE constants.
"""

import logging
from typing import Optional
import google.generativeai as genai
from shared.config import settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 8192


class GeminiClient:
    """
    Reusable Gemini API client.

    Instantiate once per agent module at module level, not per request.

    Example:
        client = GeminiClient()
        result = client.generate("Summarise this text...")
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        genai.configure(api_key=settings.gemini_api_key)
        self._generation_config = genai.types.GenerationConfig(
    temperature=temperature,
    max_output_tokens=max_tokens,
    response_mime_type="application/json",
)
        self._model = genai.GenerativeModel(
            model_name=model,
            generation_config=self._generation_config,
        )
        logger.info("GeminiClient ready — model=%s", model)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Send a text prompt and return the model response.

        Args:
            prompt:        The user task or question.
            system_prompt: Optional role/instruction context.

        Returns:
            Plain text response string.

        Raises:
            RuntimeError: If the Gemini API call fails.
        """
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        try:
            response = self._model.generate_content(full_prompt)
            logger.debug("Response received (%d chars)", len(response.text))
            return response.text
        except Exception as exc:
            logger.error("Gemini call failed: %s", exc)
            raise RuntimeError(f"Gemini call failed: {exc}") from exc

    def generate_with_file(
        self,
        prompt: str,
        file_bytes: bytes,
        mime_type: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Send a prompt together with a file (PDF or image).

        Args:
            prompt:        Instruction for what to do with the file.
            file_bytes:    Raw file content.
            mime_type:     e.g. "application/pdf" or "image/jpeg"
            system_prompt: Optional role/instruction context.

        Returns:
            Plain text response string.

        Raises:
            RuntimeError: If the Gemini API call fails.
        """
        intro = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        content_parts = [
            intro,
            {"mime_type": mime_type, "data": file_bytes},
        ]
        try:
            response = self._model.generate_content(content_parts)
            logger.debug("File response received (%d chars)", len(response.text))
            return response.text
        except Exception as exc:
            logger.error("Gemini file call failed: %s", exc)
            raise RuntimeError(f"Gemini file call failed: {exc}") from exc
