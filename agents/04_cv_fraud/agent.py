"""
CV fraud detection agent — Problem 04.
Customer: Persowerk Deutschland GmbH (Saarbrücken)
GDPR Art. 22: never makes automated adverse hiring decisions.
human_review_required always forced to True.
Accepts PDF or image CVs.
"""

import logging
from datetime import date
from shared.gemini_client import GeminiClient
from shared.utils import clean_json_response
from .prompts import SYSTEM_PROMPT, CV_ANALYSIS_PROMPT

logger = logging.getLogger(__name__)
_client = GeminiClient()

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}

VALID_RECOMMENDATIONS = {"proceed", "verify_further", "reject"}
VALID_DOCUMENT_TYPES = {"cv", "certificate", "other"}


def analyze_cv(file_bytes: bytes, mime_type: str) -> dict:
    """
    Analyse a CV for AI generation and fraud indicators.

    Args:
        file_bytes: Raw bytes of the CV file.
        mime_type:  MIME type e.g. "application/pdf".

    Returns:
        Dict with keys: candidate_name, fraud_risk_score,
        fraud_risk_level, ai_generated_indicators,
        inconsistencies_found, experience_verification_flags,
        overall_assessment, recommendation, human_review_required.

    Raises:
        ValueError:   If file empty or mime type unsupported.
        RuntimeError: If Gemini API call fails.
    """
    if not file_bytes:
        raise ValueError("File is empty")

    if mime_type not in SUPPORTED_MIME_TYPES:
        raise ValueError(f"Unsupported type: {mime_type}. Use PDF, JPG, PNG.")

    logger.info("Analysing CV — mime=%s size=%d bytes", mime_type, len(file_bytes))

    today = date.today()
    date_context = (
        f"Today's date: {today.strftime('%d %B %Y')} (current year: {today.year})\n\n"
        f"IMPORTANT — date interpretation rules:\n"
        f"- Year-only dates like \"{today.year}\" cover the full calendar year. "
        f"Entries dated \"{today.year}\" or \"YYYY–{today.year}\" are NOT future-dated — "
        f"they are ongoing or recently completed. Do NOT flag them as suspicious.\n"
        f"- Only flag a date as future if it is explicitly beyond {today.year}, "
        f"or if a specific month/day is given that is clearly after today.\n"
        f"- \"Present\", \"current\", \"ongoing\", or a year equal to {today.year} "
        f"all mean the person is still in that role or programme right now.\n\n"
    )
    prompt = date_context + CV_ANALYSIS_PROMPT

    raw = _client.generate_with_file(
        prompt=prompt,
        file_bytes=file_bytes,
        mime_type=mime_type,
        system_prompt=SYSTEM_PROMPT,
    )

    result = clean_json_response(raw)

    # GDPR Art. 22 hard override — human must review, no exceptions
    result["human_review_required"] = True

    # Sanitize enums
    if result.get("recommendation") not in VALID_RECOMMENDATIONS:
        result["recommendation"] = "verify_further"
    if result.get("document_type") not in VALID_DOCUMENT_TYPES:
        result["document_type"] = "cv"

    # Normalise renamed field: support both old and new key names
    if "experience_verification_flags" in result and "document_flags" not in result:
        result["document_flags"] = result.pop("experience_verification_flags")
    result.setdefault("document_flags", [])

    logger.info(
        "Document analysed — type=%s candidate=%s risk=%s score=%.2f",
        result.get("document_type"),
        result.get("candidate_name"),
        result.get("fraud_risk_level"),
        result.get("fraud_risk_score", 0),
    )

    return result


def analyze_cv_batch(files: list[dict]) -> list[dict]:
    """
    Analyse multiple CVs for fraud indicators.

    Args:
        files: List of dicts with keys:
               "filename" (str)
               "file_bytes" (bytes)
               "mime_type" (str)

    Returns:
        List of result dicts, one per file.
        Each result is analyze_cv() output plus "filename".
        Failed files return error dict with filename.
    """
    if not files:
        raise ValueError("files list cannot be empty")

    results = []
    for file in files:
        filename = file.get("filename", "unknown")
        try:
            result = analyze_cv(
                file_bytes=file["file_bytes"],
                mime_type=file["mime_type"],
            )
            result["filename"] = filename
            results.append(result)
        except Exception as exc:
            logger.error("Failed to analyse %s: %s", filename, exc)
            results.append({
                "filename": filename,
                "error": str(exc),
                "fraud_risk_level": "high",
                "human_review_required": True,
            })

    logger.info(
        "CV batch complete — %d files, %d errors",
        len(results),
        sum(1 for result in results if "error" in result),
    )
    return results
