"""
Marketing content agent - Problem 06.
Customer: Dr. Theiss Naturwaren GmbH (Homburg)

Generates short-form video content briefs for TikTok
and Instagram Reels with correct safe zone margins.

No personal data processed. Fully stateless.
"""

import logging

from shared.gemini_client import GeminiClient
from shared.utils import clean_json_response, truncate_for_prompt

from .prompts import CONTENT_BRIEF_PROMPT, SYSTEM_PROMPT

logger = logging.getLogger(__name__)
_client = GeminiClient()

VALID_PLATFORMS = {"TikTok", "Instagram Reels", "Both"}


def generate_content_brief(
    product_name: str,
    campaign_goal: str,
    target_platform: str,
    target_audience: str = "general consumers aged 25-45",
) -> dict:
    """
    Generate a short-form video content brief with safe zone specs.

    Args:
        product_name:    Name of the Dr. Theiss product.
        campaign_goal:   e.g. "increase awareness", "drive sales"
        target_platform: "TikTok", "Instagram Reels", or "Both"
        target_audience: Description of target demographic.

    Returns:
        Dict with keys: product_name, platform, hook_text,
        hook_type, main_message, call_to_action,
        content_duration_seconds, scene_breakdown,
        safe_zone_instructions, suggested_hashtags,
        music_mood, platform_specs, content_warnings.

    Raises:
        ValueError:   If required inputs are empty or platform invalid.
        RuntimeError: If Gemini API call fails.
    """
    if not product_name or not product_name.strip():
        raise ValueError("product_name cannot be empty")
    if not campaign_goal or not campaign_goal.strip():
        raise ValueError("campaign_goal cannot be empty")
    if target_platform not in VALID_PLATFORMS:
        raise ValueError(
            f"target_platform must be one of: {sorted(VALID_PLATFORMS)}"
        )

    prompt = CONTENT_BRIEF_PROMPT.format(
        product_name=product_name.strip(),
        campaign_goal=truncate_for_prompt(campaign_goal, max_chars=500),
        target_platform=target_platform,
        target_audience=target_audience.strip(),
    )

    logger.info(
        "Generating content brief - product=%s platform=%s",
        product_name,
        target_platform,
    )

    raw = _client.generate(prompt, system_prompt=SYSTEM_PROMPT)
    result = clean_json_response(raw)

    # Ensure platform_specs always contains safe-zone data.
    if "platform_specs" not in result:
        result["platform_specs"] = {
            "tiktok": {
                "text_safe_zone": "x=20 y=160 w=540 h=740",
                "ui_overlay_margin": "avoid right 100px, bottom 220px",
                "recommended_duration": "21-34 seconds for best completion rate",
            },
            "instagram": {
                "text_safe_zone": "x=20 y=80 w=980 h=1580",
                "ui_overlay_margin": "avoid right 80px, bottom 260px",
                "recommended_duration": "15-30 seconds for best completion rate",
            },
        }

    if not isinstance(result.get("content_warnings"), list):
        result["content_warnings"] = []

    logger.info(
        "Brief generated - platform=%s duration=%ds scenes=%d",
        result.get("platform"),
        result.get("content_duration_seconds", 0),
        len(result.get("scene_breakdown", [])),
    )

    return result
