"""
Prompt-injection-resistant email agent — Problem 10.
Customer: Rheinmetall (cross-account security capability)

Processes job application emails securely.
Detects prompt injection attempts.
Checks for required documents: CV, residence permit,
work permit, criminal record statement.

GDPR Art. 32: Security by design — untrusted input is never
executed as instructions. Fully stateless.
"""

import logging
from shared.gemini_client import GeminiClient
from shared.utils import clean_json_response, truncate_for_prompt
from .prompts import SYSTEM_PROMPT, PROCESS_EMAIL_PROMPT

logger = logging.getLogger(__name__)
_client = GeminiClient()

VALID_RISK_LEVELS = {"safe", "suspicious", "blocked"}

# Known injection phrases — pre-screen before even calling Gemini
# This is a defence-in-depth measure on top of the model's own detection
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
    """
    Pre-screen email text for known injection patterns before Gemini call.

    This is a defence-in-depth layer — the model also detects injection,
    but we catch obvious attempts early to avoid sending them to the API.

    Args:
        text: Raw email body text.

    Returns:
        List of matched injection phrases. Empty list if none found.
    """
    text_lower = text.lower()
    return [
        pattern
        for pattern in _INJECTION_PATTERNS
        if pattern in text_lower
    ]


def process_applicant_email(
    email_body: str,
    attachments_summary: str = "No attachments listed",
) -> dict:
    """
    Process a job application email securely.

    Detects prompt injection, summarises the application safely,
    and checks whether all required documents are present.

    Args:
        email_body:           Full text of the received email.
        attachments_summary:  Description of attached files
                              e.g. "CV.pdf, passport_scan.jpg"

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

    # Defence layer 1: pre-screen for known injection patterns
    # If caught here, we can short-circuit without calling Gemini
    matched_patterns = _prescreen_for_injection(email_body)

    if matched_patterns:
        logger.warning(
            "Injection pre-screened — patterns found: %s", matched_patterns
        )
        # Return blocked result immediately — no API call needed
        return {
            "injection_detected": True,
            "injection_indicators": matched_patterns,
            "sanitized_summary": (
                "BLOCKED — prompt injection attempt detected during pre-screening."
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

    # Defence layer 2: Gemini with injection-resistant system prompt
    safe_body = truncate_for_prompt(email_body, max_chars=2500)
    prompt = PROCESS_EMAIL_PROMPT.format(
        email_body=safe_body,
        attachments_summary=attachments_summary,
    )

    logger.info("Processing application email — length=%d chars", len(email_body))

    raw = _client.generate(prompt, system_prompt=SYSTEM_PROMPT)
    result = clean_json_response(raw)

    # Sanitize risk level — reject unexpected values
    if result.get("security_risk_level") not in VALID_RISK_LEVELS:
        result["security_risk_level"] = "suspicious"

    # If model detected injection but pre-screen missed it, log it
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
