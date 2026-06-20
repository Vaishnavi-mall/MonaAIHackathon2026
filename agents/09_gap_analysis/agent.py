"""
Competitive gap analysis agent — Problem 09.
Customer: Dr. Theiss Naturwaren GmbH (Homburg)

Takes product portfolio and competitor info as text.
Returns structured white-space gap analysis.
Fully stateless — no data written to disk.
"""

import logging
from shared.gemini_client import GeminiClient
from shared.utils import clean_json_response, truncate_for_prompt
from .prompts import SYSTEM_PROMPT, GAP_ANALYSIS_PROMPT

logger = logging.getLogger(__name__)
_client = GeminiClient()


def analyze_competitive_gaps(
    product_portfolio: str,
    competitor_info: str,
    market_category: str,
) -> dict:
    """
    Identify white-space gaps competitors are not filling.

    Args:
        product_portfolio: Description of Dr. Theiss current products.
        competitor_info:   Known competitor products and positioning.
        market_category:   e.g. "natural cold remedies" or "herbal supplements"

    Returns:
        Dict with keys: market_category, our_products_summary,
        competitor_products_summary, gaps_identified,
        recommended_new_products, white_space_summary,
        confidence_level.

    Raises:
        ValueError:   If any required input is empty.
        RuntimeError: If Gemini API call fails.
    """
    if not product_portfolio or not product_portfolio.strip():
        raise ValueError("product_portfolio cannot be empty")
    if not competitor_info or not competitor_info.strip():
        raise ValueError("competitor_info cannot be empty")
    if not market_category or not market_category.strip():
        raise ValueError("market_category cannot be empty")

    prompt = GAP_ANALYSIS_PROMPT.format(
        market_category=market_category.strip(),
        product_portfolio=truncate_for_prompt(product_portfolio, max_chars=1500),
        competitor_info=truncate_for_prompt(competitor_info, max_chars=1500),
    )

    logger.info("Running gap analysis — category=%s", market_category)

    raw = _client.generate(prompt, system_prompt=SYSTEM_PROMPT)
    result = clean_json_response(raw)

    # Clamp confidence to valid range in case model goes out of bounds
    confidence = float(result.get("confidence_level", 0.5))
    result["confidence_level"] = max(0.0, min(1.0, confidence))

    logger.info(
        "Gap analysis complete — gaps=%d recommendations=%d confidence=%.2f",
        len(result.get("gaps_identified", [])),
        len(result.get("recommended_new_products", [])),
        result.get("confidence_level", 0),
    )

    return result
