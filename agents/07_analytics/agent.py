"""
Customer analytics agent - Problem 07.
Customer: Dr. Theiss Naturwaren GmbH (Homburg)

Ingests customer data summaries, detects behavioural patterns,
generates targeting signals for optimal ad timing.

GDPR note: This agent works on anonymised aggregated data summaries
only - never individual customer records.
Stateless - no data written to disk.
"""

import logging
from datetime import date

from shared.gemini_client import GeminiClient
from shared.utils import clean_json_response, truncate_for_prompt

from .prompts import ANALYTICS_PROMPT, SYSTEM_PROMPT

logger = logging.getLogger(__name__)
_client = GeminiClient()


def analyze_customer_data(
    data_summary: str,
    product_name: str,
    market_category: str = "consumer health products",
) -> dict:
    """
    Detect behavioural patterns and generate ad targeting signals.

    Args:
        data_summary:     Anonymised aggregated customer data as text.
                          e.g. purchase frequency, seasonal patterns,
                          regional distribution, age bands.
        product_name:     Name of the product to analyse for.
        market_category:  Product category for context.

    Returns:
        Dict with keys: product_name, analysis_date, key_segments,
        optimal_ad_timing, targeting_signals, predicted_lift_percentage,
        recommended_channels, seasonal_patterns, data_quality_notes,
        human_review_required.

    Raises:
        ValueError:   If data_summary or product_name is empty.
        RuntimeError: If Gemini API call fails.
    """
    if not data_summary or not data_summary.strip():
        raise ValueError("data_summary cannot be empty")
    if not product_name or not product_name.strip():
        raise ValueError("product_name cannot be empty")

    prompt = ANALYTICS_PROMPT.format(
        product_name=product_name.strip(),
        market_category=market_category.strip(),
        data_summary=truncate_for_prompt(data_summary, max_chars=2500),
    )

    logger.info(
        "Analysing customer data - product=%s category=%s",
        product_name,
        market_category,
    )

    raw = _client.generate(prompt, system_prompt=SYSTEM_PROMPT)
    result = clean_json_response(raw)

    if not result.get("analysis_date"):
        result["analysis_date"] = date.today().isoformat()

    lift = float(result.get("predicted_lift_percentage", 0))
    result["predicted_lift_percentage"] = max(0.0, min(50.0, lift))

    if not isinstance(result.get("targeting_signals"), list):
        result["targeting_signals"] = []

    logger.info(
        "Analytics complete - segments=%d signals=%d lift=%.1f%%",
        len(result.get("key_segments", [])),
        len(result.get("targeting_signals", [])),
        result.get("predicted_lift_percentage", 0),
    )

    return result
