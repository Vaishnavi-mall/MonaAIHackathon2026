# GDPR & EU AI Act — compliance notes

## Prototype status
This is a hackathon prototype. Production deployment requires a signed
Data Processing Agreement (DPA) and legal review.

## Data handling
- Stateless: no input is written to disk or database
- No PII logging: prompt content is never written to logs
- File uploads: held in memory per request, then discarded
- Retention: DATA_RETENTION_DAYS=0 in .env

## Per-agent compliance

| Agent | Regulation | Requirement |
|-------|-----------|-------------|
| 01 Invoice | GDPR Art. 5 | Data minimisation |
| 03 Work permit | GDPR Art. 9 | Special category data |
| 04 CV fraud | GDPR Art. 22 | No automated adverse decisions |
| 05 Interview | Directive 2000/78/EC | No discriminatory questions |
| 10 Secure email | GDPR Art. 32 | Prompt injection controls |

## EU AI Act (Annex III — high-risk)
Recruitment tools are high-risk. Mitigation for this prototype:
every agent output includes human_review_required = true.
