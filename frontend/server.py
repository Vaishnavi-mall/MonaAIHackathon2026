"""
frontend/server.py
------------------
FastAPI application — one route per agent.
Agent logic is imported from agents/ as each agent is built.

Run with: uvicorn frontend.server:app --reload --port 8000
"""

import logging
from importlib import import_module
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

# Numeric agent directory names require dynamic imports.
# Each import is guarded so the server starts even when only some agents
# are available — unfinished agents return 501 Not Implemented.

def _not_ready(name):
    def _stub(*_, **kw):
        raise NotImplementedError(f"Agent '{name}' is not deployed yet. kwargs={list(kw)}")
    return _stub

try:
    invoice_agent = import_module("agents.01_invoice.agent")
    process_invoice = invoice_agent.process_invoice
    process_invoice_batch = invoice_agent.process_invoice_batch
except ImportError:
    logger.warning("Agent 01 (invoice) not available")
    process_invoice = process_invoice_batch = _not_ready("01_invoice")

try:
    shift_agent = import_module("agents.02_shift.agent")
    find_shift_replacements = shift_agent.find_shift_replacements
    parse_schedule_file = shift_agent.parse_schedule_file
except ImportError:
    logger.warning("Agent 02 (shift) not available")
    find_shift_replacements = parse_schedule_file = _not_ready("02_shift")

try:
    permit_agent = import_module("agents.03_work_permit.agent")
    validate_work_permit = permit_agent.validate_work_permit
    validate_permit_batch = permit_agent.validate_permit_batch
except ImportError:
    logger.warning("Agent 03 (work_permit) not available")
    validate_work_permit = validate_permit_batch = _not_ready("03_work_permit")

try:
    cv_agent = import_module("agents.04_cv_fraud.agent")
    analyze_cv = cv_agent.analyze_cv
    analyze_cv_batch = cv_agent.analyze_cv_batch
except ImportError:
    logger.warning("Agent 04 (cv_fraud) not available")
    analyze_cv = analyze_cv_batch = _not_ready("04_cv_fraud")

try:
    generate_interview_pack = import_module(
        "agents.05_interview.agent"
    ).generate_interview_pack
except ImportError:
    logger.warning("Agent 05 (interview) not available")
    generate_interview_pack = _not_ready("05_interview")

try:
    generate_content_brief = import_module(
        "agents.06_marketing.agent"
    ).generate_content_brief
except ImportError:
    logger.warning("Agent 06 (marketing) not available")
    generate_content_brief = _not_ready("06_marketing")

try:
    analyze_customer_data = import_module(
        "agents.07_analytics.agent"
    ).analyze_customer_data
except ImportError:
    logger.warning("Agent 07 (analytics) not available")
    analyze_customer_data = _not_ready("07_analytics")

try:
    calculate_dynamic_price = import_module(
        "agents.08_pricing.agent"
    ).calculate_dynamic_price
except ImportError:
    logger.warning("Agent 08 (pricing) not available")
    calculate_dynamic_price = _not_ready("08_pricing")

try:
    analyze_competitive_gaps = import_module(
        "agents.09_gap_analysis.agent"
    ).analyze_competitive_gaps
except ImportError:
    logger.warning("Agent 09 (gap_analysis) not available")
    analyze_competitive_gaps = _not_ready("09_gap_analysis")

try:
    process_applicant_email = import_module(
        "agents.10_secure_email.agent"
    ).process_applicant_email
except ImportError:
    logger.warning("Agent 10 (secure_email) not available")
    process_applicant_email = _not_ready("10_secure_email")

app = FastAPI(title="Mona AI Hackathon", version="1.0.0")

# Allow browser requests from localhost during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Quick liveness check — confirms the server is running."""
    return {"status": "ok"}


@app.post("/api/agent01")
async def agent01_invoice(files: list[UploadFile] = File(...)):
    """
    Invoice processing — single or multiple files.
    Returns list of results, one per file.
    Accepts PDF, JPG, PNG, DOCX.
    Nothing written to disk.
    """
    try:
        if not files:
            return JSONResponse(
                {"error": "No files uploaded"}, status_code=400
            )

        file_list = []
        for file in files:
            file_bytes = await file.read()
            file_list.append({
                "filename": file.filename or "unknown",
                "file_bytes": file_bytes,
                "mime_type": file.content_type,
            })

        results = process_invoice_batch(file_list)
        return JSONResponse({
            "total": len(results),
            "results": results,
        })

    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except RuntimeError as exc:
        logger.error("Agent01 batch failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/agent02")
async def agent02_shift(
    absent_staff: str = Form(...),
    shift_details: str = Form(...),
    schedule_file: UploadFile = File(...),
):
    """
    Shift replacement agent.
    Accepts Excel schedule + form fields for absent staff and shift.
    Nothing written to disk.
    """
    try:
        file_bytes = await schedule_file.read()

        if not file_bytes:
            return JSONResponse({"error": "Schedule file is empty"}, status_code=400)

        schedule_text = parse_schedule_file(file_bytes)

        result = find_shift_replacements(
            schedule_data=schedule_text,
            absent_staff=absent_staff,
            shift_details=shift_details,
        )
        return JSONResponse(result)

    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except RuntimeError as exc:
        logger.error("Agent02 failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/agent05")
async def agent05_interview(request: Request):
    """
    Interview support agent endpoint.
    Accepts JSON body: {"job_description": "..."}
    Returns structured interview pack.
    """
    try:
        body = await request.json()
        job_description = body.get("job_description", "").strip()

        if not job_description:
            return JSONResponse(
                {"error": "job_description is required"}, status_code=400
            )

        result = generate_interview_pack(job_description)
        return JSONResponse(result)

    except ValueError as exc:
        # Input validation errors — user's fault, return 400
        return JSONResponse({"error": str(exc)}, status_code=400)

    except RuntimeError as exc:
        # API failures — our fault, return 500
        logger.error("Agent05 failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/agent03")
async def agent03_work_permit(files: list[UploadFile] = File(...)):
    """
    Work permit validation — single or multiple files.
    Returns list of results, one per file.
    GDPR Art. 9: special category data. Nothing written to disk.
    """
    try:
        if not files:
            return JSONResponse(
                {"error": "No files uploaded"}, status_code=400
            )

        file_list = []
        for file in files:
            file_bytes = await file.read()
            file_list.append({
                "filename": file.filename or "unknown",
                "file_bytes": file_bytes,
                "mime_type": file.content_type,
            })

        results = validate_permit_batch(file_list)
        return JSONResponse({
            "total": len(results),
            "results": results,
        })

    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except RuntimeError as exc:
        logger.error("Agent03 batch failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/agent04")
async def agent04_cv_fraud(files: list[UploadFile] = File(...)):
    """
    CV fraud detection — single or multiple files.
    Returns list of results, one per file.
    GDPR Art. 22: human review always required. Nothing written to disk.
    """
    try:
        if not files:
            return JSONResponse(
                {"error": "No files uploaded"}, status_code=400
            )

        file_list = []
        for file in files:
            file_bytes = await file.read()
            file_list.append({
                "filename": file.filename or "unknown",
                "file_bytes": file_bytes,
                "mime_type": file.content_type,
            })

        results = analyze_cv_batch(file_list)
        return JSONResponse({
            "total": len(results),
            "results": results,
        })

    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except RuntimeError as exc:
        logger.error("Agent04 batch failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/agent06")
async def agent06_marketing(request: Request):
    """Marketing content brief generator for Dr. Theiss."""
    try:
        body = await request.json()
        product_name = body.get("product_name", "").strip()
        campaign_goal = body.get("campaign_goal", "").strip()
        target_platform = body.get("target_platform", "").strip()
        target_audience = body.get(
            "target_audience", "general consumers aged 25-45"
        ).strip()

        if not all([product_name, campaign_goal, target_platform]):
            return JSONResponse(
                {"error": "product_name, campaign_goal and target_platform required"},
                status_code=400,
            )

        result = generate_content_brief(
            product_name=product_name,
            campaign_goal=campaign_goal,
            target_platform=target_platform,
            target_audience=target_audience,
        )
        return JSONResponse(result)

    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except RuntimeError as exc:
        logger.error("Agent06 failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/agent07")
async def agent07_analytics(request: Request):
    """Customer analytics and targeting signal generator for Dr. Theiss."""
    try:
        body = await request.json()
        data_summary = body.get("data_summary", "").strip()
        product_name = body.get("product_name", "").strip()
        market_category = body.get(
            "market_category", "consumer health products"
        ).strip()

        if not all([data_summary, product_name]):
            return JSONResponse(
                {"error": "data_summary and product_name are required"},
                status_code=400,
            )

        result = analyze_customer_data(
            data_summary=data_summary,
            product_name=product_name,
            market_category=market_category,
        )
        return JSONResponse(result)

    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except RuntimeError as exc:
        logger.error("Agent07 failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/agent10")
async def agent10_secure_email(request: Request):
    """
    Secure email processing for Rheinmetall.
    Detects prompt injection and checks for required documents.
    Stateless — nothing written to disk.
    """
    try:
        body = await request.json()
        email_body = body.get("email_body", "").strip()
        attachments_summary = body.get("attachments_summary", "").strip()

        if not email_body:
            return JSONResponse(
                {"error": "email_body is required"}, status_code=400
            )

        result = process_applicant_email(email_body, attachments_summary)
        return JSONResponse(result)

    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except RuntimeError as exc:
        logger.error("Agent10 failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/agent09")
async def agent09_gap_analysis(request: Request):
    """Competitive gap analysis for Dr. Theiss."""
    try:
        body = await request.json()
        product_portfolio = body.get("product_portfolio", "").strip()
        competitor_info = body.get("competitor_info", "").strip()
        market_category = body.get("market_category", "").strip()

        if not all([product_portfolio, competitor_info, market_category]):
            return JSONResponse(
                {"error": "product_portfolio, competitor_info and market_category are all required"},
                status_code=400,
            )

        result = analyze_competitive_gaps(
            product_portfolio=product_portfolio,
            competitor_info=competitor_info,
            market_category=market_category,
        )
        return JSONResponse(result)

    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except RuntimeError as exc:
        logger.error("Agent09 failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/agent08")
async def agent08_pricing(request: Request):
    """Dynamic pricing agent for Dr. Theiss."""
    try:
        body = await request.json()
        base_price = float(body.get("base_price", 0))
        product_name = body.get("product_name", "").strip()
        signals = body.get("signals", {})

        if not product_name:
            return JSONResponse(
                {"error": "product_name is required"}, status_code=400
            )
        if base_price <= 0:
            return JSONResponse(
                {"error": "base_price must be greater than 0"}, status_code=400
            )
        if not signals:
            return JSONResponse(
                {"error": "at least one signal is required"}, status_code=400
            )

        result = calculate_dynamic_price(base_price, product_name, signals)
        return JSONResponse(result)

    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except RuntimeError as exc:
        logger.error("Agent08 failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/")
def serve_frontend():
    """Serve the single-page demo UI."""
    return FileResponse("frontend/index.html")


# ── Agent routes — uncomment each as the agent is built ──────────────────────

# Agent 01 through Agent 05 routes are implemented above.
# TODO: add remaining routes as agents are completed
