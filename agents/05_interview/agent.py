"""
agents/05_interview/agent.py
----------------------------
Interview support agent — Problem 05.
Customer: Kohlpharma GmbH (Merzig)

Takes a plain-text job description.
Returns a structured interview pack ready for the hiring manager.

GDPR note: No personal data is processed in this agent.
EU AI Act: Output always includes human_review_notice (Annex III high-risk).
"""

import logging
from shared.gemini_client import GeminiClient
from shared.utils import clean_json_response, truncate_for_prompt
from .prompts import SYSTEM_PROMPT, INTERVIEW_PACK_PROMPT

logger = logging.getLogger(__name__)

# Instantiate once at module level — not on every request
_client = GeminiClient()


def generate_interview_pack(job_description: str) -> dict:
    """
    Generate a structured interview pack from a job description.

    Args:
        job_description: Plain text job posting from the hiring manager.
                         Typically copied from Indeed or similar.

    Returns:
        Dict with keys:
            role_summary           (str)
            seniority_level        (str)
            technical_questions    (list[str], length 5)
            behavioural_questions  (list[str], length 3)
            red_flags              (list[str], length 3)
            suggested_scoring_criteria (str)
            human_review_notice    (str)

    Raises:
        ValueError:   If job_description is empty or model returns bad JSON.
        RuntimeError: If the Gemini API call fails.
    """
    # Validate input before calling the API
    if not job_description or not job_description.strip():
        raise ValueError("job_description cannot be empty")

    if len(job_description.strip()) < 50:
        raise ValueError(
            "job_description is too short — please paste the full job posting"
        )

    # Truncate if extremely long to stay within prompt limits
    safe_description = truncate_for_prompt(job_description, max_chars=2500)

    prompt = INTERVIEW_PACK_PROMPT.format(job_description=safe_description)

    logger.info(
        "Generating interview pack — input_length=%d chars", len(job_description)
    )

    raw_response = _client.generate(prompt, system_prompt=SYSTEM_PROMPT)
    result = clean_json_response(raw_response)

    logger.info("Interview pack generated successfully")
    return result
