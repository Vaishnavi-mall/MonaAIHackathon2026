# Mona AI Hackathon

Ten Gemini-powered AI agent prototypes for HR, operations, and healthcare workflows.

## Prerequisites

- Python 3.10 or higher
- pip
- An internet connection (the frontend loads SheetJS from CDN for Excel parsing)

## Setup after cloning

### 1. Clone the repository

```bash
git clone <repo-url>
cd MonaAIHackathon2026
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
```

Activate it:

- **macOS / Linux**
  ```bash
  source .venv/bin/activate
  ```
- **Windows**
  ```bash
  .venv\Scripts\activate
  ```

You should see `(.venv)` in your terminal prompt.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

This installs FastAPI, Uvicorn, the Gemini SDK, openpyxl, and all other required packages.

### 4. Create your `.env` file

Create a file called `.env` in the project root (same folder as `requirements.txt`):

```bash
cp .env .env.backup   # optional — back up the existing file first
```

Open `.env` and set the following values:

```
GEMINI_API_KEY="your-gemini-api-key-here"
APP_ENV=development
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=10
DATA_RETENTION_DAYS=0
```

To get a Gemini API key: visit [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey), sign in with a Google account, and create a new key.

> **Never commit `.env` to git.** It is already listed in `.gitignore`.

### 5. Run the server

```bash
make run
```

Or without `make`:

```bash
uvicorn frontend.server:app --reload --port 8000
```

### 6. Open the app

Go to [http://localhost:8000](http://localhost:8000) in your browser.

---

## Running tests

```bash
make test
```

Or:

```bash
pytest agents/ -v
```

---

## Project structure

```
MonaAIHackathon2026/
├── agents/
│   ├── 01_invoice/        Invoice processing
│   ├── 02_shift/          Shift replacement
│   ├── 03_work_permit/    Work permit validation
│   ├── 04_cv_fraud/       CV & certificate fraud detection
│   ├── 05_interview/      Interview question generation
│   ├── 06_marketing/      Marketing content briefs
│   ├── 07_analytics/      Customer analytics
│   ├── 08_pricing/        Dynamic pricing
│   ├── 09_gap_analysis/   Competitive gap analysis
│   └── 10_secure_email/   Secure email processing
├── frontend/
│   ├── index.html         Single-page UI
│   └── server.py          FastAPI server
├── shared/
│   ├── gemini_client.py   Gemini API wrapper
│   └── utils.py           Shared helpers
├── requirements.txt
├── Makefile
└── .env                   Your local secrets (not committed)
```

---

## Troubleshooting

**`ModuleNotFoundError` on startup**
Make sure your virtual environment is activated (`source .venv/bin/activate`) and you ran `pip install -r requirements.txt` inside it.

**`GEMINI_API_KEY` not found / API errors**
Check that your `.env` file exists in the project root and contains a valid key. The server reads it automatically on startup.

**Port 8000 already in use**
Run on a different port:
```bash
uvicorn frontend.server:app --reload --port 8001
```
Then open [http://localhost:8001](http://localhost:8001).

**Excel upload / name validation not working**
The frontend loads SheetJS from a CDN to parse `.xlsx` files. Make sure you have an active internet connection when using the Shift Replacement agent.

**Agent returns 501 Not Implemented**
That agent module has not been deployed yet. Only agents with a completed `agent.py` are active.
