SYSTEM_PROMPT = """
You are a senior market research analyst specialising in
consumer health and natural remedy products.
You identify white-space gaps competitors are not filling.

RULES:
1. Be specific — name actual product types, not vague categories.
2. Score opportunity size: small / medium / large.
3. Score difficulty to enter: low / medium / high.
4. Always return valid JSON matching the exact schema.
"""

GAP_ANALYSIS_PROMPT = """
Perform a competitive gap analysis for this company.

MARKET CATEGORY: {market_category}

OUR PRODUCT PORTFOLIO:
{product_portfolio}

COMPETITOR INFORMATION:
{competitor_info}

Return a JSON object with EXACTLY these keys:
{{
  "market_category": "category name",
  "our_products_summary": ["product 1", "product 2"],
  "competitor_products_summary": ["competitor product 1"],
  "gaps_identified": [
    {{
      "gap_name": "specific unmet need or product type",
      "opportunity_size": "small or medium or large",
      "difficulty": "low or medium or high",
      "reasoning": "one sentence why this gap exists"
    }}
  ],
  "recommended_new_products": [
    {{
      "name": "specific product name",
      "rationale": "one sentence why Dr. Theiss should make this",
      "priority": "high or medium or low"
    }}
  ],
  "white_space_summary": "2-3 sentence executive summary of the biggest opportunity",
  "confidence_level": 0.0 to 1.0
}}

gaps_identified: minimum 3, maximum 6.
recommended_new_products: minimum 2, maximum 4, ranked by priority.
confidence_level: reflects how complete the competitor data provided was.

Return ONLY the JSON. No preamble, no markdown.
"""
