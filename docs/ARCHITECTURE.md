# Architecture

## Stack
- AI: Gemini Flash 2.5
- Backend: Python 3.12 + FastAPI
- Frontend: Single static HTML (no framework)
- Database: None (stateless)

## Request flow
Browser → FastAPI → Agent module → GeminiClient → Gemini API → JSON response

## Key decisions
1. One GeminiClient in shared/ — API key configured once
2. Prompts in prompts.py — separated from business logic
3. All agents return typed dicts — never raw strings
4. No database — GDPR-friendly, simple to demo
