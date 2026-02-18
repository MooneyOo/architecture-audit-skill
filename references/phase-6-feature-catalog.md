# Phase 6: Feature Catalog & API Reference

## Overview

Map every user-facing and system feature to its code implementation. Build comprehensive API reference with endpoints, authentication, request/response schemas.

## Actions

1. Scan all route definitions and controller handlers
2. Build feature catalog linking UI → API → Backend → DB
3. Document each API endpoint with method, path, auth, request/response
4. Map features to database tables

## Patterns to Detect

### Route Patterns

```
# Express/Koa
router.get('/path', handler)
app.get('/path', handler)

# NestJS
@Get('path')
@Post('path')

# FastAPI
@app.get('/path')
@app.post('/path')

# Django
path('path/', view_func)
urlpatterns = [...]

# Next.js API
export default function handler(req, res)
```

### Authentication Patterns
```
# JWT
Authorization: Bearer <token>

# API Key
x-api-key: <key>

# Session
Cookie: session_id=<id>

# OAuth
Authorization: Bearer <oauth_token>
```

## Output Section

Populates: `## 6. Feature Catalog & API Reference`

### Feature Catalog Table

| # | Feature Name | UI Entry Point | API Endpoint(s) | Backend Logic | DB Tables |
|---|--------------|----------------|-----------------|---------------|-----------|
| 1 | User Registration | `/register` | `POST /api/auth/register` | `auth.controller.ts:register` | users |
| 2 | User Login | `/login` | `POST /api/auth/login` | `auth.controller.ts:login` | users, sessions |
| 3 | Profile Update | `/profile` | `PUT /api/users/:id` | `user.controller.ts:update` | users |
| 4 | Create Order | `/orders/new` | `POST /api/orders` | `order.controller.ts:create` | orders, line_items |
| 5 | View Orders | `/orders` | `GET /api/orders` | `order.controller.ts:list` | orders |

### API Reference Table

| Method | Endpoint | Auth Required | Request Body | Success Response | Error Codes |
|--------|----------|---------------|--------------|------------------|-------------|
| POST | `/api/auth/register` | No | `{ email, password, name }` | `201 { user, token }` | 400, 409 |
| POST | `/api/auth/login` | No | `{ email, password }` | `200 { user, token }` | 401, 404 |
| GET | `/api/users/me` | Yes | - | `200 { user }` | 401 |
| PUT | `/api/users/me` | Yes | `{ name?, email? }` | `200 { user }` | 400, 401 |
| GET | `/api/orders` | Yes | - | `200 { orders[] }` | 401 |
| POST | `/api/orders` | Yes | `{ items[], shipping? }` | `201 { order }` | 400, 401 |

### Request/Response Schema Example

#### POST /api/auth/register

**Request:**
```json
{
  "email": "string (required, valid email)",
  "password": "string (required, min 8 chars)",
  "name": "string (optional, max 100 chars)"
}
```

**Success Response (201):**
```json
{
  "user": {
    "id": "uuid",
    "email": "string",
    "name": "string",
    "created_at": "datetime"
  },
  "token": "jwt_string"
}
```

**Error Responses:**
- `400` - Invalid input data
- `409` - Email already exists

## Grep Commands

```bash
# Find all API routes (Express)
grep -rE "router\.(get|post|put|delete|patch)" --include="*.ts" --include="*.js"

# Find all API routes (NestJS)
grep -rE "@(Get|Post|Put|Delete|Patch)\(" --include="*.ts"

# Find all API routes (FastAPI)
grep -rE "@app\.(get|post|put|delete|patch)" --include="*.py"

# Find all API routes (Django)
grep -rE "path\(|url\(" --include="*.py"

# Find route files
find . -path ./node_modules -prune -o -name "*route*" -print
find . -path ./node_modules -prune -o -name "*controller*" -print

# Find authentication requirements
grep -rE "authenticate|auth\.required|@UseGuards|@LoginRequired" --include="*.ts" --include="*.js" --include="*.py"

# List all endpoints with methods
grep -rE "(GET|POST|PUT|DELETE|PATCH).*\//" --include="*.ts" --include="*.js"
```

## Implementation

**Script:** `scripts/feature_catalog.py`

### Usage

```bash
# Full analysis (JSON output)
python scripts/feature_catalog.py /path/to/project

# Markdown output with all sections
python scripts/feature_catalog.py /path/to/project --format markdown

# Specific sections
python scripts/feature_catalog.py /path/to/project --endpoints --format markdown
python scripts/feature_catalog.py /path/to/project --features --format markdown
python scripts/feature_catalog.py /path/to/project --api-reference --format markdown
python scripts/feature_catalog.py /path/to/project --flows --format markdown
```

### Supported Frameworks

| Framework | Detection | Endpoint Discovery | Schema Detection |
|-----------|-----------|-------------------|------------------|
| FastAPI | requirements.txt, pyproject.toml | `@router.get("/path")` | Pydantic models |
| Express.js | package.json | `router.get('/path', handler)` | TypeScript interfaces |
| Fastify | package.json | `fastify.get('/path', opts, handler)` | JSON schemas |
| NestJS | package.json | `@Get('path')` decorator | DTOs |
| Django | requirements.txt | `path('url/', view)` | Serializers |
| Next.js | package.json | File-based routing | TypeScript |

### Output Sections

1. **6.0 Discovered Endpoints** - Raw endpoint discovery with method, path, handler, file
2. **6.1 Feature Catalog** - Features mapped to UI, API, backend logic, DB tables
3. **6.2 API Reference** - Detailed API docs with auth, schemas, error codes
4. **6.3 Route Flows** - Request flow diagrams with Mermaid sequence diagrams

## Self-Check

- [x] All routes/endpoints discovered
- [x] Feature catalog complete with all user features
- [x] API reference table complete
- [x] Authentication requirements documented
- [x] Request/response schemas for each endpoint
- [x] Features mapped to database tables
- [x] All referenced files exist

## Validation Results (2025-02-17)

**Test Project:** `/Users/mooney/Documents/vibecoding/jirakpi_v1`

| Check | Result | Details |
|-------|--------|---------|
| Framework Detection | PASS | FastAPI detected |
| Endpoints Found | PASS | 18 endpoints |
| Feature Catalog | PASS | 18 features |
| Auth Detection | PASS | 17/18 with auth info |
| Schema Detection | PASS | 14/18 with schemas |
| Route Flows | PASS | 18 flows generated |
