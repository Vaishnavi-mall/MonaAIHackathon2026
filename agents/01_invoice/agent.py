"""
agents/01_invoice/agent.py
---------------------------
Invoice processing agent — Problem 01.
Customer: Globus Group (St. Wendel)

Accepts PDF, image, or DOCX invoice.
Extracts key fields and routes to the correct internal department.

GDPR Article 5: Data minimisation — only fields needed for routing
are extracted. No data is stored after the request completes.

NOTE on DOCX: Gemini does not accept DOCX files directly.
DOCX files are converted to plain text (including table content)
using python-docx, then sent as a text prompt instead of a file upload.

Root cause of the previous bug: python-docx paragraphs only extracts
body text — all table cells (where invoices store amounts, dates, line
items) were silently dropped. The fix reads both paragraphs AND tables.
"""

import io
import logging

from shared.gemini_client import GeminiClient
from shared.utils import clean_json_response
from .prompts import PROCESS_INVOICE_PROMPT, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# One client instance per module — not recreated on every request
_client = GeminiClient()

# MIME types Gemini accepts for direct file upload (vision)
_GEMINI_SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}

# DOCX must be handled separately — Gemini rejects this MIME type
_DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

# All MIME types this agent accepts from the user
SUPPORTED_MIME_TYPES = _GEMINI_SUPPORTED_MIME_TYPES | {_DOCX_MIME_TYPE}

VALID_DEPARTMENTS = {"IT", "Finance", "Operations", "Facilities", "HR", "Other"}


def _extract_text_from_docx(file_bytes: bytes) -> str:
    """
    Extract all readable text from a DOCX file — paragraphs AND tables.

    Why both: invoices store critical data (amounts, dates, line items,
    vendor details) inside tables. python-docx .paragraphs only returns
    body text outside tables — silently dropping everything in a table cell.
    This function reads both sources and combines them in document order.

    Args:
        file_bytes: Raw bytes of the DOCX file.

    Returns:
        Plain text string with all content, table cells joined by " | ".

    Raises:
        ValueError:   If the file cannot be parsed or contains no text.
        RuntimeError: If python-docx is not installed.
    """
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError(
            "python-docx is not installed. Run: pip install python-docx"
        ) from exc

    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ValueError(f"Could not open DOCX file: {exc}") from exc

    lines = []

    # Walk the document body in order — paragraphs and tables are siblings
    # in doc.element.body, so we iterate the XML children to preserve order
    from docx.oxml.ns import qn
    for child in doc.element.body:
        # Paragraph element
        if child.tag == qn("w:p"):
            text = "".join(
                node.text for node in child.iter(qn("w:t")) if node.text
            ).strip()
            if text:
                lines.append(text)

        # Table element — join each row's cells with " | "
        elif child.tag == qn("w:tbl"):
            for row in child.iter(qn("w:tr")):
                cells = []
                for cell in row.iter(qn("w:tc")):
                    cell_text = "".join(
                        node.text for node in cell.iter(qn("w:t")) if node.text
                    ).strip()
                    if cell_text:
                        cells.append(cell_text)
                if cells:
                    lines.append(" | ".join(cells))

    if not lines:
        raise ValueError(
            "DOCX file appears to be empty or contains no readable text"
        )

    extracted = "\n".join(lines)
    logger.debug("Extracted %d chars from DOCX (%d lines)", len(extracted), len(lines))
    return extracted


def _build_docx_prompt(extracted_text: str) -> str:
    """
    Wrap extracted DOCX text in clear delimiters and append the task prompt.

    Args:
        extracted_text: Plain text extracted from the DOCX file.

    Returns:
        Full prompt string ready to send to Gemini as a text request.
    """
    return (
        "The following text was extracted from an invoice document (DOCX format).\n"
        "Table cells are separated by ' | ' characters.\n\n"
        "--- INVOICE CONTENT START ---\n"
        f"{extracted_text}\n"
        "--- INVOICE CONTENT END ---\n\n"
        + PROCESS_INVOICE_PROMPT
    )


def process_invoice(file_bytes: bytes, mime_type: str, filename: str = "") -> dict:
    """
    Extract data from an invoice and route it to the correct department.

    Handles PDF and images via Gemini file upload (vision).
    Handles DOCX by extracting text first, then sending as a text prompt.

    Args:
        file_bytes: Raw bytes of the uploaded invoice file.
        mime_type:  MIME type e.g. "application/pdf", "image/png".
        filename:   Original filename, used for logging only.

    Returns:
        Dict with keys:
            vendor_name            (str)
            invoice_number         (str)
            invoice_date           (str, ISO format or "not_found")
            due_date               (str, ISO format or "not_found")
            total_amount           (str, with currency symbol)
            currency               (str)
            line_items             (list[str])
            department             (str: IT|Finance|Operations|Facilities|HR|Other)
            category               (str)
            confidence             (float, 0.0-1.0)
            routing_reason         (str)
            language               (str, e.g. "de" or "en")
            human_review_required  (bool)

    Raises:
        ValueError:   If file is empty, MIME type unsupported, or DOCX unreadable.
        RuntimeError: If the Gemini API call fails.
    """
    if not file_bytes:
        raise ValueError("File is empty — please upload a valid invoice")

    if mime_type not in SUPPORTED_MIME_TYPES:
        raise ValueError(
            f"Unsupported file type: {mime_type}. "
            "Accepted formats: PDF, JPG, PNG, DOCX"
        )

    logger.info(
        "Processing invoice — file=%s mime=%s size=%d bytes",
        filename, mime_type, len(file_bytes),
    )

    # ── Route based on file type ──────────────────────────────────────────────

    if mime_type == _DOCX_MIME_TYPE:
        # DOCX: extract paragraphs + table cells → embed in text prompt
        # Gemini rejects DOCX uploads — this is the correct workaround
        logger.debug("DOCX detected — extracting text+tables before Gemini call")
        extracted_text = _extract_text_from_docx(file_bytes)
        prompt = _build_docx_prompt(extracted_text)
        raw_response = _client.generate(prompt, system_prompt=SYSTEM_PROMPT)

    else:
        # PDF / image: send directly as a file (Gemini vision handles it)
        raw_response = _client.generate_with_file(
            prompt=PROCESS_INVOICE_PROMPT,
            file_bytes=file_bytes,
            mime_type=mime_type,
            system_prompt=SYSTEM_PROMPT,
        )

    # ── Parse and validate response ───────────────────────────────────────────

    result = clean_json_response(raw_response)

    # Guard: model occasionally returns a department outside our valid set
    if result.get("department") not in VALID_DEPARTMENTS:
        logger.warning(
            "Unexpected department '%s' — defaulting to Other",
            result.get("department"),
        )
        result["department"] = "Other"
        result["human_review_required"] = True

    # Business rule: high-value invoices always require human review
    # This is a hard rule — not delegated to the model's confidence score
    amount_str = str(result.get("total_amount", ""))
    try:
        amount_digits = float(
            "".join(c for c in amount_str if c.isdigit() or c == ".")
        )
        if amount_digits > 10000:
            logger.info(
                "High-value invoice (%.2f) — forcing human_review_required=True",
                amount_digits,
            )
            result["human_review_required"] = True
    except ValueError:
        pass  # Amount not parseable — leave human_review_required as model set it

    logger.info(
        "Invoice processed — vendor=%s department=%s confidence=%.2f",
        result.get("vendor_name"),
        result.get("department"),
        result.get("confidence", 0),
    )

    return result


def process_invoice_batch(files: list[dict]) -> list[dict]:
    """
    Process multiple invoices and return a result for each.

    Args:
        files: List of dicts, each with keys:
               "filename" (str)
               "file_bytes" (bytes)
               "mime_type" (str)

    Returns:
        List of result dicts. Each result is the same structure
        as process_invoice() but with "filename" added.
        Failed files return:
        {
          "filename": str,
          "error": str,
          "department": "Other",
          "human_review_required": True
        }
    """
    if not files:
        raise ValueError("files list cannot be empty")

    results = []
    for file in files:
        filename = file.get("filename", "unknown")
        try:
            result = process_invoice(
                file_bytes=file["file_bytes"],
                mime_type=file["mime_type"],
                filename=filename,
            )
            result["filename"] = filename
            results.append(result)
        except Exception as exc:
            logger.error("Failed to process %s: %s", filename, exc)
            results.append({
                "filename": filename,
                "error": str(exc),
                "department": "Other",
                "human_review_required": True,
            })

    logger.info(
        "Batch complete — %d files, %d errors",
        len(results),
        sum(1 for result in results if "error" in result),
    )
    return results
