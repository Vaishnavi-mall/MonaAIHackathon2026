"""
Shift replacement agent — Problem 02.
Customer: Universitätsklinikum des Saarlandes / UKS (Homburg)

Reads hospital schedule data, finds available qualified staff,
drafts a ready-to-send contact message.

Input: schedule as text, absent staff name, shift details.
All stateless — no data written to disk.
"""

import logging
import io
from shared.gemini_client import GeminiClient
from shared.utils import clean_json_response, truncate_for_prompt
from .prompts import SYSTEM_PROMPT, SHIFT_REPLACEMENT_PROMPT

logger = logging.getLogger(__name__)
_client = GeminiClient()

VALID_URGENCY_LEVELS = {"low", "medium", "high", "critical"}


def _parse_excel_schedule(file_bytes: bytes) -> str:
    """
    Convert Excel schedule to plain text for the prompt.

    Args:
        file_bytes: Raw bytes of the .xlsx file.

    Returns:
        Tab-separated text representation of all sheets.

    Raises:
        ValueError:   If file cannot be parsed as Excel.
        RuntimeError: If openpyxl is not installed.
    """
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError(
            "openpyxl not installed. Run: pip install openpyxl"
        ) from exc

    try:
        wb = openpyxl.load_workbook(
            io.BytesIO(file_bytes), read_only=True, data_only=True
        )
    except Exception as exc:
        raise ValueError(f"Could not read Excel file: {exc}") from exc

    lines = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        lines.append(f"=== Sheet: {sheet_name} ===")
        for row in ws.iter_rows(values_only=True):
            # Skip fully empty rows
            cells = [str(c) if c is not None else "" for c in row]
            if any(c.strip() for c in cells):
                lines.append("\t".join(cells))

    if not lines:
        raise ValueError("Excel file appears to be empty")

    return "\n".join(lines)


def find_shift_replacements(
    schedule_data: str,
    absent_staff: str,
    shift_details: str,
) -> dict:
    """
    Find available staff to cover an urgent shift gap.

    Args:
        schedule_data: Plain text of the hospital schedule
                       (use parse_schedule_file for Excel input).
        absent_staff:  Name and role of the person who called in sick.
        shift_details: Date, time, ward, and role needed.

    Returns:
        Dict with keys: shift_date, shift_time, required_role,
        available_staff, recommended_contact_order, draft_message,
        urgency_level, human_review_required.

    Raises:
        ValueError:   If any required input is empty.
        RuntimeError: If Gemini API call fails.
    """
    if not schedule_data or not schedule_data.strip():
        raise ValueError("schedule_data cannot be empty")
    if not absent_staff or not absent_staff.strip():
        raise ValueError("absent_staff cannot be empty")
    if not shift_details or not shift_details.strip():
        raise ValueError("shift_details cannot be empty")

    safe_schedule = truncate_for_prompt(schedule_data, max_chars=3000)

    prompt = SHIFT_REPLACEMENT_PROMPT.format(
        schedule_data=safe_schedule,
        absent_staff=absent_staff,
        shift_details=shift_details,
    )

    logger.info(
        "Finding shift replacement — absent=%s shift=%s",
        absent_staff, shift_details,
    )

    raw = _client.generate(prompt, system_prompt=SYSTEM_PROMPT)
    result = clean_json_response(raw)

    # Sanitize urgency level
    if result.get("urgency_level") not in VALID_URGENCY_LEVELS:
        result["urgency_level"] = "high"

    # Always require human review for patient-safety critical decisions
    result["human_review_required"] = True

    logger.info(
        "Replacement found — urgency=%s candidates=%d",
        result.get("urgency_level"),
        len(result.get("available_staff", [])),
    )

    return result


def parse_schedule_file(file_bytes: bytes) -> str:
    """
    Parse an uploaded Excel schedule file into plain text.

    Convenience wrapper used by the API route before calling
    find_shift_replacements.

    Args:
        file_bytes: Raw bytes of the .xlsx schedule file.

    Returns:
        Plain text schedule ready to pass to find_shift_replacements.
    """
    return _parse_excel_schedule(file_bytes)
