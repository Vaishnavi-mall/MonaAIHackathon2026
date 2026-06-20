"""
agents/03_work_permit/agent.py
-------------------------------
Work permit validation agent — Problem 03.
Customer: Leistenschneider Personaldienstleistungen GmbH (Saarbrücken)

Accepts a PDF or image of a work permit.
Returns structured validation result with confidence score.

GDPR Article 9: Work permits contain special category data
(nationality, immigration status). This agent is stateless —
no data is stored after the request completes.
human_review_required is always true regardless of model output.
"""

import logging
from datetime import date

from shared.gemini_client import GeminiClient
from shared.utils import clean_json_response

from .prompts import SYSTEM_PROMPT, VALIDATE_PERMIT_PROMPT

logger = logging.getLogger(__name__)

# Instantiate once at module level — not on every request
_client = GeminiClient()

# Supported MIME types for permit documents
SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}


def validate_work_permit(file_bytes: bytes, mime_type: str) -> dict:
    """
    Validate a work permit document using Gemini vision.

    Args:
        file_bytes: Raw bytes of the uploaded PDF or image.
        mime_type:  MIME type string e.g. "application/pdf", "image/jpeg".

    Returns:
        Dict with keys:
            is_valid_permit        (bool)
            confidence_percentage  (float, 0-100)
            permit_type            (str)
            valid_until            (str, ISO date or "not_found")
            valid_from             (str, ISO date or "not_found")
            issuing_authority      (str)
            holder_name            (str)
            document_number        (str)
            flags                  (list[str])
            decision               (str: APPROVED | REJECTED | NEEDS_REVIEW)
            decision_reason        (str)
            human_review_required  (bool, always True)

    Raises:
        ValueError:   If file is empty or mime type not supported.
        RuntimeError: If the Gemini API call fails.
    """
    if not file_bytes:
        raise ValueError("File is empty — please upload a valid document")

    if mime_type not in SUPPORTED_MIME_TYPES:
        raise ValueError(
            f"Unsupported file type: {mime_type}. "
            "Accepted types: PDF, JPG, PNG"
        )

    today = date.today().isoformat()
    prompt = VALIDATE_PERMIT_PROMPT.format(current_date=today)

    logger.info(
        "Validating work permit — mime_type=%s size=%d bytes",
        mime_type,
        len(file_bytes),
    )

    raw_response = _client.generate_with_file(
        prompt=prompt,
        file_bytes=file_bytes,
        mime_type=mime_type,
        system_prompt=SYSTEM_PROMPT,
    )
    result = clean_json_response(raw_response)

    # GDPR Article 9 override — human review is non-negotiable,
    # regardless of what the model returns.
    result["human_review_required"] = True

    logger.info(
        "Validation complete — decision=%s confidence=%.1f%%",
        result.get("decision"),
        result.get("confidence_percentage", 0),
    )

    return result


def validate_permit_batch(files: list[dict]) -> list[dict]:
    """
    Validate multiple work permit documents.

    Args:
        files: List of dicts with keys:
               "filename" (str)
               "file_bytes" (bytes)
               "mime_type" (str)

    Returns:
        List of result dicts, one per file.
        Each result is validate_work_permit() output
        plus "filename" field.
        Failed files return error dict with filename.
    """
    if not files:
        raise ValueError("files list cannot be empty")

    results = []
    for file in files:
        filename = file.get("filename", "unknown")
        try:
            result = validate_work_permit(
                file_bytes=file["file_bytes"],
                mime_type=file["mime_type"],
            )
            result["filename"] = filename
            results.append(result)
        except Exception as exc:
            logger.error("Failed to validate %s: %s", filename, exc)
            results.append({
                "filename": filename,
                "error": str(exc),
                "decision": "NEEDS_REVIEW",
                "human_review_required": True,
            })

    logger.info(
        "Permit batch complete — %d files, %d errors",
        len(results),
        sum(1 for result in results if "error" in result),
    )
    return results
