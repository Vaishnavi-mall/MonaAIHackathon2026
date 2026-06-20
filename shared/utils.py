"""
shared/utils.py
---------------
Pure helper functions shared across all agents.
No side effects — easy to unit test.
"""

import json
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def clean_json_response(raw: str) -> dict:
    """
    Parse JSON from a Gemini response that may include markdown fences.

    Gemini sometimes wraps output in ```json ... ``` blocks.
    This strips those before parsing.

    Args:
        raw: Raw text from Gemini.

    Returns:
        Parsed Python dict.

    Raises:
        ValueError: If no valid JSON found.
    """
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("JSON parse failed: %s\nRaw response: %s", exc, raw[:200])
        raise ValueError(f"Model returned invalid JSON: {exc}") from exc


def truncate_for_prompt(text: str, max_chars: int = 3000) -> str:
    """
    Truncate long text to fit safely inside a Gemini prompt.

    Args:
        text:      Input text.
        max_chars: Maximum characters to keep.

    Returns:
        Original text if short enough, otherwise truncated with a notice.
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[... content truncated to fit prompt limit ...]"


def read_file_as_text(file_path: str | Path) -> str:
    """
    Read a UTF-8 text file from disk.

    Args:
        file_path: Path to the file.

    Returns:
        File contents as string.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_text(encoding="utf-8")
