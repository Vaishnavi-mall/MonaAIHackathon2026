"""
Prompt-injection-resistant email agent — Problem 10.
Customer: Rheinmetall (cross-account security capability)

Processes job application emails securely.
Detects prompt injection in email body AND each attachment's extracted text.
Classifies each attachment in isolation via a tight, bounded LLM call —
raw attachment content never reaches the main summarisation prompt.
Checks for required documents: CV, residence permit,
work permit, criminal record statement.

GDPR Art. 32: Security by design — untrusted input is never
executed as instructions. Fully stateless.
"""

import logging
from shared.gemini_client import GeminiClient
from shared.utils import clean_json_response, truncate_for_prompt
from .prompts import (
    SYSTEM_PROMPT,
    CLASSIFY_DOCUMENT_SYSTEM_PROMPT,
    CLASSIFY_DOCUMENT_PROMPT,
    PROCESS_EMAIL_PROMPT,
)

logger = logging.getLogger(__name__)
_client = GeminiClient()

VALID_RISK_LEVELS = {"safe", "suspicious", "blocked"}

VALID_DOCUMENT_TYPES = {
    "cv",
    "residence_permit",
    "work_permit",
    "criminal_record_statement",
    "unknown",
}

_INJECTION_PATTERNS = [
    "ignore previous",
    "ignore all previous",
    "ignore your instructions",
    "forget your rules",
    "you are now",
    "new instructions",
    "print your prompt",
    "reveal your system",
    "act as",
    "jailbreak",
    "disregard",
    "override",
    "pretend you are",
    "your new role",
]


def _prescreen_for_injection(text: str) -> list[str]:
    """Return matched injection patterns found in text, empty list if none."""
    text_lower = text.lower()
    return [p for p in _INJECTION_PATTERNS if p in text_lower]


def _classify_attachment(filename: str, extracted_text: str) -> str:
    """
    Classify a single attachment's document type via a tight Gemini call.

    The model is only allowed to return one field (document_type), so even
    if the attachment contains injection text it cannot influence the output
    beyond a single constrained label.

    Returns one of: cv, residence_permit, work_permit,
    criminal_record_statement, unknown.
    """
    safe_text = truncate_for_prompt(extracted_text, max_chars=1500)
    prompt = CLASSIFY_DOCUMENT_PROMPT.format(text=safe_text)

    logger.info("Classifying attachment: %s", filename)
    raw = _client.generate(prompt, system_prompt=CLASSIFY_DOCUMENT_SYSTEM_PROMPT)
    result = clean_json_response(raw)

    doc_type = result.get("document_type", "unknown")
    if doc_type not in VALID_DOCUMENT_TYPES:
        doc_type = "unknown"

    logger.info("Classified %s → %s", filename, doc_type)
    return doc_type


def _blocked_result(indicators: list[str], source: str) -> dict:
    """Return a fully blocked result dict when injection is detected."""
    return {
        "injection_detected": True,
        "injection_indicators": indicators,
        "sanitized_summary": (
            f"BLOCKED — prompt injection attempt detected in {source}."
        ),
        "documents_present": {
            "cv": False,
            "residence_permit": False,
            "work_permit": False,
            "criminal_record_statement": False,
        },
        "missing_documents": [
            "cv",
            "residence_permit",
            "work_permit",
            "criminal_record_statement",
        ],
        "application_complete": False,
        "security_risk_level": "blocked",
        "recommended_action": (
            "Do not process this email. Report to security team immediately."
        ),
    }


def process_applicant_email(
    email_body: str,
    attachments: list[dict] | None = None,
) -> dict:
    """
    Process a job application email securely.

    Pipeline:
      1. Pre-screen email body for injection patterns.
      2. Pre-screen each attachment's extracted_text for injection patterns.
      3. Classify each attachment in isolation (tight LLM call, one field output).
      4. Build documents_present from classification results in code.
      5. Pass email body + pre-classified labels (NOT raw attachment text)
         to the main summarisation prompt.
      6. Override model's documents_present with code-derived truth.

    Args:
        email_body:   Full text of the received email.
        attachments:  List of dicts, each with:
                        "filename"       (str) — original file name
                        "extracted_text" (str) — plain text extracted from the file

    Returns:
        Dict with keys: injection_detected, injection_indicators,
        sanitized_summary, documents_present, missing_documents,
        application_complete, security_risk_level, recommended_action.

    Raises:
        ValueError:   If email_body is empty.
        RuntimeError: If Gemini API call fails.
    """
    if not email_body or not email_body.strip():
        raise ValueError("email_body cannot be empty")

    if attachments is None:
        attachments = []

    # Layer 1: pre-screen email body
    matched = _prescreen_for_injection(email_body)
    if matched:
        logger.warning("Injection in email body — patterns: %s", matched)
        return _blocked_result(matched, "email body")

    # Layer 2: pre-screen each attachment before doing anything with it
    for attachment in attachments:
        filename = attachment.get("filename", "unknown")
        text = attachment.get("extracted_text", "")
        if not text:
            continue
        matched = _prescreen_for_injection(text)
        if matched:
            logger.warning(
                "Injection in attachment '%s' — patterns: %s", filename, matched
            )
            return _blocked_result(matched, f"attachment '{filename}'")

    # Layer 3: classify each attachment in isolation
    # Raw attachment text is never passed to the main prompt.
    classified: dict[str, str] = {}
    for attachment in attachments:
        filename = attachment.get("filename", "unknown")
        text = attachment.get("extracted_text", "")
        classified[filename] = (
            _classify_attachment(filename, text) if text else "unknown"
        )

    # Build documents_present from code logic, not model inference
    found_types = set(classified.values())
    documents_present = {
        "cv": "cv" in found_types,
        "residence_permit": "residence_permit" in found_types,
        "work_permit": "work_permit" in found_types,
        "criminal_record_statement": "criminal_record_statement" in found_types,
    }

    # Safe string for the prompt: code-generated labels, not user content
    classified_attachments = (
        "\n".join(f"  {fname} → {dtype}" for fname, dtype in classified.items())
        if classified
        else "  (no attachments)"
    )

    # Layer 4: main summarisation — only sees email body + pre-classified labels
    safe_body = truncate_for_prompt(email_body, max_chars=2500)
    prompt = PROCESS_EMAIL_PROMPT.format(
        email_body=safe_body,
        classified_attachments=classified_attachments,
    )

    logger.info("Processing application email — length=%d chars", len(email_body))
    raw = _client.generate(prompt, system_prompt=SYSTEM_PROMPT)
    result = clean_json_response(raw)

    # Override model's document fields with code-derived truth
    missing = [doc for doc, present in documents_present.items() if not present]
    result["documents_present"] = documents_present
    result["missing_documents"] = missing
    result["application_complete"] = len(missing) == 0

    if result.get("security_risk_level") not in VALID_RISK_LEVELS:
        result["security_risk_level"] = "suspicious"

    if result.get("injection_detected"):
        logger.warning(
            "Injection detected by model — indicators: %s",
            result.get("injection_indicators"),
        )

    logger.info(
        "Email processed — risk=%s complete=%s injection=%s",
        result.get("security_risk_level"),
        result.get("application_complete"),
        result.get("injection_detected"),
    )

    return result
