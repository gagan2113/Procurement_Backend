# Backend API Integration Guide

This file documents the current backend routes so the frontend can connect safely.

## 1) Quick Connection Info

- Local base URL: http://127.0.0.1:8000
- Swagger docs: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Content type for JSON requests: application/json
- Auth: no authentication middleware is currently applied
- CORS: enabled for all origins/methods/headers

## 2) Active Route Mounting

The app currently mounts only Purchase Request routes under:
- Prefix: /api/v1
- Router prefix: /purchase-request

So active business endpoints are under /api/v1/purchase-request...

System routes are at root level:
- GET /
- GET /health

## 3) Response Format Rules

### 3.1 Standard API envelope (most business routes)

Most purchase-request JSON routes return:

```json
{
  "success": true,
  "message": "Success",
  "data": {},
  "errors": null
}
```

### 3.2 System routes

GET / and GET /health return direct JSON (not wrapped in success/message/data/errors).

### 3.3 File download route

GET /api/v1/purchase-request/{pr_id}/pdf returns a binary PDF stream (application/pdf), not JSON.

### 3.4 Error format

- HTTP exceptions (404, etc.) return FastAPI default:

```json
{
  "detail": "Error message"
}
```

- Validation errors (422) return FastAPI validation structure:

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "description"],
      "msg": "String should have at least 10 characters",
      "input": "short"
    }
  ]
}
```

## 4) Routes With Output Examples

## 4.1 Health Check

- Method: GET
- Path: /health
- Purpose: service status
- Success status: 200

Example response:

```json
{
  "status": "healthy",
  "app": "Procurement AI System",
  "version": "1.0.0",
  "environment": "development"
}
```

## 4.2 API Root

- Method: GET
- Path: /
- Purpose: root metadata
- Success status: 200

Example response:

```json
{
  "message": "Welcome to Procurement AI System",
  "version": "1.0.0",
  "docs": "/docs",
  "health": "/health"
}
```

## 4.3 Create Purchase Request

- Method: POST
- Path: /api/v1/purchase-request
- Purpose: create PR, run AI validation, persist data, generate PDF
- Success status: 201

Request body:

```json
{
  "item_name": "Dell Latitude 5540 Laptop",
  "category": "IT Hardware",
  "quantity": 10,
  "budget": 15000,
  "description": "Laptops for the new engineering team joining in Q2."
}
```

Field constraints:
- item_name: string, min 2, max 255
- category: string, min 2, max 100
- quantity: integer, >= 1
- budget: number, > 0
- description: string, min 10, max 2000

Success response example:

```json
{
  "success": true,
  "message": "Purchase Request PR-20260331-0001 created successfully.",
  "data": {
    "id": "1f0dc0f0-1234-4a55-8d3f-111111111111",
    "pr_number": "PR-20260331-0001",
    "item_name": "Dell Latitude 5540 Laptop",
    "category": "IT Hardware",
    "quantity": 10,
    "budget": 15000.0,
    "description": "Laptops for the new engineering team joining in Q2.",
    "improved_description": "Procurement of 10 Dell Latitude 5540 laptops for incoming Q2 engineering hires.",
    "missing_fields": [],
    "budget_feedback": "Budget appears sufficient for requested quantity.",
    "ai_status": "valid",
    "status": "pending",
    "pdf_path": "pdfs/PR-20260331-0001.pdf",
    "created_at": "2026-03-31T09:10:00.000000",
    "updated_at": "2026-03-31T09:10:02.000000"
  },
  "errors": null
}
```

Validation error example (422):

```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": ["body", "quantity"],
      "msg": "Input should be greater than or equal to 1",
      "input": 0,
      "ctx": {
        "ge": 1
      }
    }
  ]
}
```

## 4.4 List Purchase Requests

- Method: GET
- Path: /api/v1/purchase-requests
- Purpose: paginated list
- Query params:
  - skip: integer >= 0 (default 0)
  - limit: integer 1..200 (default 50)
- Success status: 200

Example request:
- /api/v1/purchase-requests?skip=0&limit=20

Success response example:

```json
{
  "success": true,
  "message": "Success",
  "data": {
    "total": 2,
    "items": [
      {
        "id": "1f0dc0f0-1234-4a55-8d3f-111111111111",
        "pr_number": "PR-20260331-0002",
        "item_name": "Office Chairs",
        "category": "Furniture",
        "quantity": 12,
        "budget": 4800.0,
        "description": "Ergonomic chairs for design team.",
        "improved_description": "Procurement of 12 ergonomic office chairs for the design team.",
        "missing_fields": [],
        "budget_feedback": "Budget is within expected range.",
        "ai_status": "valid",
        "status": "pending",
        "pdf_path": "pdfs/PR-20260331-0002.pdf",
        "created_at": "2026-03-31T10:00:00.000000",
        "updated_at": "2026-03-31T10:00:01.000000"
      }
    ]
  },
  "errors": null
}
```

## 4.5 Get Purchase Request By ID

- Method: GET
- Path: /api/v1/purchase-request/{pr_id}
- Purpose: fetch one PR
- Success status: 200

Success response example:

```json
{
  "success": true,
  "message": "Success",
  "data": {
    "id": "1f0dc0f0-1234-4a55-8d3f-111111111111",
    "pr_number": "PR-20260331-0001",
    "item_name": "Dell Latitude 5540 Laptop",
    "category": "IT Hardware",
    "quantity": 10,
    "budget": 15000.0,
    "description": "Laptops for the new engineering team joining in Q2.",
    "improved_description": "Procurement of 10 Dell Latitude 5540 laptops for incoming Q2 engineering hires.",
    "missing_fields": [],
    "budget_feedback": "Budget appears sufficient for requested quantity.",
    "ai_status": "valid",
    "status": "pending",
    "pdf_path": "pdfs/PR-20260331-0001.pdf",
    "created_at": "2026-03-31T09:10:00.000000",
    "updated_at": "2026-03-31T09:10:02.000000"
  },
  "errors": null
}
```

Not found example (404):

```json
{
  "detail": "Purchase Request with ID 'unknown-id' not found."
}
```

## 4.6 Update Purchase Request

- Method: PUT
- Path: /api/v1/purchase-request/{pr_id}
- Purpose: update PR fields, optionally rerun AI when core fields change
- Success status: 200

Request body (partial update allowed):

```json
{
  "quantity": 12,
  "budget": 18000,
  "status": "active"
}
```

Allowed fields:
- item_name
- category
- quantity
- budget
- description
- status (pending, active, approved, rejected, closed)

Success response example:

```json
{
  "success": true,
  "message": "Purchase Request PR-20260331-0001 updated successfully.",
  "data": {
    "id": "1f0dc0f0-1234-4a55-8d3f-111111111111",
    "pr_number": "PR-20260331-0001",
    "item_name": "Dell Latitude 5540 Laptop",
    "category": "IT Hardware",
    "quantity": 12,
    "budget": 18000.0,
    "description": "Laptops for the new engineering team joining in Q2.",
    "improved_description": "Updated AI-enhanced text...",
    "missing_fields": [],
    "budget_feedback": "Budget remains sufficient.",
    "ai_status": "valid",
    "status": "active",
    "pdf_path": "pdfs/PR-20260331-0001.pdf",
    "created_at": "2026-03-31T09:10:00.000000",
    "updated_at": "2026-03-31T09:45:00.000000"
  },
  "errors": null
}
```

Not found example (404):

```json
{
  "detail": "Purchase Request with ID 'unknown-id' not found."
}
```

## 4.7 Download PR PDF

- Method: GET
- Path: /api/v1/purchase-request/{pr_id}/pdf
- Purpose: download generated PDF
- Success status: 200
- Response type: binary file stream

Success response headers example:

```text
Content-Type: application/pdf
Content-Disposition: attachment; filename="PR-20260331-0001.pdf"
```

Not found examples (404):

```json
{
  "detail": "Purchase Request 'unknown-id' not found."
}
```

```json
{
  "detail": "PDF not yet generated for this Purchase Request."
}
```

## 5) Enums Frontend Should Use

PR status values:
- pending
- active
- approved
- rejected
- closed

AI status values:
- valid
- needs_review
- pending

## 6) Frontend Integration Notes

- Use /api/v1 prefix for all purchase-request API calls.
- For list API, call /api/v1/purchase-requests (plural path).
- Expect wrapped JSON (success/message/data/errors) for purchase-request endpoints except PDF download.
- Handle 422 validation errors from FastAPI separately in UI forms.
- For PDF download, request as blob/file in frontend client.

## 7) Route Modules Present but Not Active Yet

These files exist but are currently empty and not mounted in the app entrypoint:
- backend/routes/bid.py
- backend/routes/chat.py
- backend/routes/dashboard.py
- backend/routes/finance.py
- backend/routes/invoice.py
- backend/routes/payment.py
- backend/routes/po.py
- backend/routes/rfq.py
- backend/routes/vendor.py

Current app mounting is defined in backend/main.py and only includes purchase-request router.
