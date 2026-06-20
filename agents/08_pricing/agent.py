"""
Dynamic pricing agent — Problem 08.
Customer: Dr. Theiss Naturwaren GmbH (Homburg)

Adjusts product prices based on external signals:
weather, events, supply chain, season.

Guardrails: max +25% / min -40% of base price.
Changes > 15% require human approval.
Stateless — no data written to disk.
"""

import logging
from datetime import datetime, timedelta, timezone

from shared.gemini_client import GeminiClient
from shared.utils import clean_json_response

from .prompts import DYNAMIC_PRICING_PROMPT, SYSTEM_PROMPT

logger = logging.getLogger(__name__)
_client = GeminiClient()

# Hard price guardrails — enforced in code, not just in the prompt
_MAX_INCREASE_FACTOR = 1.25  # never more than +25%
_MIN_DECREASE_FACTOR = 0.60  # never less than -40%
_HUMAN_APPROVAL_THRESHOLD = 0.15  # changes > 15% need approval


def _format_signals(signals: dict) -> str:
    """
    Format the signals dict into readable text for the prompt.

    Args:
        signals: Dict with keys like weather, events,
                 supply_chain, season, competitor_price.

    Returns:
        Formatted multi-line string.
    """
    lines = []
    for key, value in signals.items():
        lines.append(f"- {key.replace('_', ' ').title()}: {value}")
    return "\n".join(lines) if lines else "No signals provided"


def _apply_guardrails(
    base_price: float,
    recommended_price: float,
    result: dict,
) -> dict:
    """
    Enforce hard price limits regardless of model recommendation.

    These are code-level guardrails — the model's suggestion is
    overridden if it breaches the limits set by business rules.

    Args:
        base_price:        Original product price.
        recommended_price: Price suggested by the model.
        result:            Full result dict to mutate.

    Returns:
        Updated result dict with guardrails applied.
    """
    max_price = round(base_price * _MAX_INCREASE_FACTOR, 2)
    min_price = round(base_price * _MIN_DECREASE_FACTOR, 2)

    if recommended_price > max_price:
        logger.warning(
            "Price %.2f exceeds max %.2f — clamping", recommended_price, max_price
        )
        result["recommended_price"] = max_price
        result["guardrail_flags"].append(
            f"Price clamped to maximum allowed (+25%): {max_price} EUR"
        )
        result["human_approval_required"] = True

    elif recommended_price < min_price:
        logger.warning(
            "Price %.2f below min %.2f — clamping", recommended_price, min_price
        )
        result["recommended_price"] = min_price
        result["guardrail_flags"].append(
            f"Price clamped to minimum allowed (-40%): {min_price} EUR"
        )
        result["human_approval_required"] = True

    else:
        result["recommended_price"] = round(recommended_price, 2)

    # Recalculate derived values after applying code-level limits.
    final_price = result["recommended_price"]
    change_pct = round(((final_price - base_price) / base_price) * 100, 2)
    result["price_change_percentage"] = change_pct
    result["price_direction"] = (
        "increase" if change_pct > 0 else "decrease" if change_pct < 0 else "hold"
    )

    if abs(change_pct) > _HUMAN_APPROVAL_THRESHOLD * 100:
        result["human_approval_required"] = True

    return result


def calculate_dynamic_price(
    base_price: float,
    product_name: str,
    signals: dict,
) -> dict:
    """
    Calculate a dynamic price adjustment based on external signals.

    Args:
        base_price:   Current base price in EUR.
        product_name: Name of the product being priced.
        signals:      Dict of external signals. Supported keys:
                      weather, events, supply_chain, season,
                      competitor_price, demand_trend.

    Returns:
        Dict with keys: product_name, base_price, recommended_price,
        price_change_percentage, price_direction, signals_applied,
        reasoning, guardrail_flags, valid_until,
        human_approval_required.

    Raises:
        ValueError:   If base_price <= 0 or product_name empty.
        RuntimeError: If Gemini API call fails.
    """
    if base_price <= 0:
        raise ValueError("base_price must be greater than 0")
    if not product_name or not product_name.strip():
        raise ValueError("product_name cannot be empty")
    if not signals:
        raise ValueError("At least one pricing signal is required")

    signals_text = _format_signals(signals)
    prompt = DYNAMIC_PRICING_PROMPT.format(
        product_name=product_name.strip(),
        base_price=base_price,
        signals=signals_text,
    )

    logger.info(
        "Calculating dynamic price — product=%s base=%.2f signals=%d",
        product_name,
        base_price,
        len(signals),
    )

    raw = _client.generate(prompt, system_prompt=SYSTEM_PROMPT)
    result = clean_json_response(raw)

    # Ensure guardrail_flags is always a list
    if not isinstance(result.get("guardrail_flags"), list):
        result["guardrail_flags"] = []

    # Apply hard code-level guardrails on top of model output
    recommended = float(result.get("recommended_price", base_price))
    result = _apply_guardrails(base_price, recommended, result)

    # Set valid_until to 24 hours from now if model didn't set it correctly
    try:
        datetime.fromisoformat(result.get("valid_until", ""))
    except (ValueError, TypeError):
        result["valid_until"] = (
            datetime.now(timezone.utc) + timedelta(hours=24)
        ).isoformat()

    logger.info(
        "Price calculated — %.2f → %.2f (%.1f%%) approval_required=%s",
        base_price,
        result.get("recommended_price"),
        result.get("price_change_percentage", 0),
        result.get("human_approval_required"),
    )

    return result
