# Procurement AI Backend

## Command to Run the Project

Run these commands from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
Copy-Item .env.example .env
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open these URLs after startup:
- API docs: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health check: http://127.0.0.1:8000/health

## Project Overview

Procurement AI Backend is a FastAPI service for creating and managing purchase requests (PRs). It combines:
- FastAPI for REST APIs
- SQLAlchemy + SQLite for persistence
- LangGraph + Azure OpenAI for AI-assisted validation and enhancement
- ReportLab for PDF generation of each PR

The current app entrypoint mounts the Purchase Request routes under `/api/v1`.

## Key Features

- Create, list, get, and update Purchase Requests
- AI validation pipeline for PR details
- Improved description and budget feedback from AI
- Automatic PDF generation per request
- Standard API response envelope (`success`, `message`, `data`, `errors`)

## Tech Stack

- Python
- FastAPI
- Uvicorn
- SQLAlchemy
- Pydantic v2
- LangChain + LangGraph
- Azure OpenAI
- ReportLab

## Environment Variables

Create `.env` in the repository root (you can copy from `.env.example`).

Required Azure OpenAI settings:
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT_NAME` (default in example: `gpt-4o`)
- `AZURE_OPENAI_API_VERSION`

Other settings:
- `DATABASE_URL` (default: `sqlite:///./procurement.db`)
- `APP_NAME`
- `APP_VERSION`
- `APP_ENV`
- `DEBUG`
- `PDF_DIR` (default: `pdfs`)

## API Endpoints

Base URL: `http://127.0.0.1:8000`

System:
- `GET /`
- `GET /health`

Purchase Request (mounted with `/api/v1`):
- `POST /api/v1/purchase-request`
- `GET /api/v1/purchase-requests`
- `GET /api/v1/purchase-request/{pr_id}`
- `PUT /api/v1/purchase-request/{pr_id}`
- `GET /api/v1/purchase-request/{pr_id}/pdf`

## Example: Create a Purchase Request

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/purchase-request" \
  -H "Content-Type: application/json" \
  -d '{
    "item_name": "Dell Latitude 5540 Laptop",
    "category": "IT Hardware",
    "quantity": 10,
    "budget": 15000,
    "description": "Laptops for the new engineering team joining in Q2."
  }'
```

Typical response shape:

```json
{
  "success": true,
  "message": "Purchase Request PR-YYYYMMDD-0001 created successfully.",
  "data": {
    "id": "uuid",
    "pr_number": "PR-YYYYMMDD-0001",
    "item_name": "Dell Latitude 5540 Laptop",
    "category": "IT Hardware",
    "quantity": 10,
    "budget": 15000.0,
    "description": "Laptops for the new engineering team joining in Q2.",
    "improved_description": "...",
    "missing_fields": [],
    "budget_feedback": "...",
    "ai_status": "valid",
    "status": "pending",
    "pdf_path": "pdfs/PR-YYYYMMDD-0001.pdf",
    "created_at": "...",
    "updated_at": "..."
  },
  "errors": null
}
```

## Data and Generated Files

- SQLite database file: `procurement.db`
- Generated PDFs: `pdfs/`

These runtime artifacts are local files and should not be pushed to GitHub.

## Project Structure

```text
backend/
  main.py
  config/
  db/
  llm/
  models/
  repositories/
  routes/
  schemas/
  services/
  tests/
```

## Notes

- If Azure OpenAI credentials are missing or invalid, the API may fail at startup or return AI fallback behavior.
- The repository includes additional route modules (vendor, rfq, invoice, etc.), but the current app entrypoint mounts only purchase request routes.
