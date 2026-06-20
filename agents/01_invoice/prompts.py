"""
agents/01_invoice/prompts.py
-----------------------------
Prompt templates for the invoice processing agent (Problem 01).
Customer: Globus Group (St. Wendel)

Separation of prompts from logic allows:
- Wording adjustments without touching business logic
- Easy compliance review of what the model is instructed to do
- Simple A/B testing of routing logic
"""

SYSTEM_PROMPT = """
You are an expert accounts payable specialist and document analyst.
Your job is to read supplier invoices and extract key information,
then route them to the correct internal department for approval.

DEPARTMENT ROUTING RULES — use these exactly:
  IT          → software licenses, cloud services, hardware, telecom,
                IT consulting, cybersecurity, SaaS subscriptions
  Finance     → consulting fees, legal fees, audit, banking, insurance,
                financial services, large one-off payments > 10000
  Operations  → office supplies, printing, cleaning, maintenance,
                logistics, shipping, raw materials, manufacturing
  Facilities  → utilities (gas, electricity, water), rent, building
                maintenance, security services, parking
  HR          → recruitment fees, training, travel, accommodation,
                employee benefits, catering, team events
  Other       → anything that does not clearly fit the above

STRICT RULES:
1. Extract all fields you can find — use "not_found" if missing.
2. Amounts must include the currency symbol or code.
3. Confidence reflects how clearly the invoice matches a department.
4. If confidence < 0.8 set human_review_required to true.
5. Always return valid JSON matching the exact schema.
6. Dates in ISO format YYYY-MM-DD or "not_found".
"""

PROCESS_INVOICE_PROMPT = """
Read this invoice document carefully and extract all information.

Analyze the content and return a JSON object with EXACTLY these keys:
{{
  "vendor_name": "supplier company name or not_found",
  "invoice_number": "invoice reference number or not_found",
  "invoice_date": "YYYY-MM-DD or not_found",
  "due_date": "YYYY-MM-DD or not_found",
  "total_amount": "amount with currency e.g. 1234.56 EUR or not_found",
  "currency": "EUR or USD or GBP etc, or not_found",
  "line_items": ["item 1 description", "item 2 description"],
  "department": "IT or Finance or Operations or Facilities or HR or Other",
  "category": "specific category e.g. Software License or Utilities or Office Supplies",
  "confidence": 0.0 to 1.0 as a number,
  "routing_reason": "one sentence explaining why this goes to that department",
  "language": "de or en or other",
  "human_review_required": true or false
}}

Set human_review_required to true if:
- confidence is below 0.8
- total amount is above 10000
- the document does not look like a real invoice
- any critical field is missing

Return ONLY the JSON object. No preamble, no explanation, no markdown.
"""
