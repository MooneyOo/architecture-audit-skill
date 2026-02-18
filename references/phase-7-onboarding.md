# Phase 7: Developer Onboarding

## Overview

Document everything a new developer or AI agent needs to start working with the codebase: environment setup, auth model, happy paths, and error handling.

## Automated Analysis Scripts

This phase includes four Python scripts for automated analysis:

### Script Usage

```bash
# 1. Environment Analysis
python scripts/environment_analyzer.py <project_path> --format markdown

# 2. Authentication Analysis
python scripts/auth_analyzer.py <project_path> --format markdown

# 3. Happy Path Tracing
python scripts/happy_path_tracer.py <project_path> --format markdown

# 4. Error Handling Analysis
python scripts/error_handler_analyzer.py <project_path> --format markdown
```

### Script Outputs

| Script | Output Sections |
|--------|-----------------|
| `environment_analyzer.py` | 7.1 Prerequisites, 7.2 Environment Variables, 7.3 Startup Sequence |
| `auth_analyzer.py` | 7.5 Authentication & Authorization |
| `happy_path_tracer.py` | 7.4 Core User Flow (Happy Path) |
| `error_handler_analyzer.py` | 7.6 Error Handling Patterns |

## Actions

1. List all environment variables (from .env.example, config files, code references)
2. Document startup sequence (install, configure, start)
3. Trace a core user flow end-to-end with file paths
4. Document authentication and authorization model
5. Document error handling patterns

## Patterns to Detect

### Environment Variables
```
# JavaScript/TypeScript
process.env.VARIABLE_NAME

# Python
os.environ['VARIABLE_NAME']
os.getenv('VARIABLE_NAME')

# Config patterns
config('VARIABLE_NAME')
settings.VARIABLE_NAME
```

### Startup Patterns
```
# Node.js
npm install → npm run dev / npm start
yarn install → yarn dev / yarn start

# Python
pip install -r requirements.txt → python manage.py runserver
poetry install → poetry run python main.py

# Docker
docker-compose up
docker build . && docker run
```

### Auth Patterns
```
# JWT
Authorization: Bearer <token>
jsonwebtoken.verify()

# Session
req.session.user
sessionMiddleware

# OAuth
passport.authenticate('google')
authService.oauth()

# API Keys
x-api-key header
```

## Output Section

Populates: `## 7. Developer Onboarding & Operational Context`

### Prerequisites Table

| Requirement | Version | Installation |
|-------------|---------|--------------|
| Node.js | 18.x | `brew install node` |
| PostgreSQL | 14.x | `brew install postgresql` |
| Redis | 7.x | `brew install redis` |

### Environment Variables Table

| Variable | Purpose | Example | Required | Default |
|----------|---------|---------|----------|---------|
| DATABASE_URL | PostgreSQL connection | `postgresql://user:pass@localhost:5432/db` | Yes | - |
| REDIS_URL | Redis connection | `redis://localhost:6379` | No | `redis://localhost:6379` |
| JWT_SECRET | JWT signing key | `your-secret-key` | Yes | - |
| PORT | Server port | `3000` | No | `3000` |
| NODE_ENV | Environment | `development` | No | `development` |

### Startup Sequence

```bash
# 1. Clone and install dependencies
git clone <repo>
cd <project>
npm install

# 2. Configure environment
cp .env.example .env
# Edit .env with your values

# 3. Initialize database
npm run db:migrate
npm run db:seed  # optional

# 4. Start development server
npm run dev
```

### Core User Flow (Happy Path)

**Flow:** User Registration → Login → Create Resource

| Step | Component | File Path | Description |
|------|-----------|-----------|-------------|
| 1 | Frontend Form | `src/pages/Register.tsx` | User fills registration form |
| 2 | API Client | `src/api/auth.ts` | POST to `/api/auth/register` |
| 3 | Route Handler | `src/routes/auth.ts` | Routes to controller |
| 4 | Controller | `src/controllers/auth.controller.ts:register()` | Validates input, calls service |
| 5 | Service | `src/services/auth.service.ts:register()` | Hashes password, creates user |
| 6 | Repository | `src/repositories/user.repository.ts:create()` | Inserts into database |
| 7 | Response | `src/controllers/auth.controller.ts` | Returns user + JWT token |

### Authentication & Authorization Table

| Aspect | Implementation | File Path |
|--------|----------------|-----------|
| Auth Type | JWT Bearer Token | `src/middleware/auth.ts` |
| Token Generation | `jsonwebtoken.sign()` | `src/services/auth.service.ts` |
| Token Validation | `jsonwebtoken.verify()` | `src/middleware/auth.ts` |
| Role Model | Role-based (admin, user) | `src/models/user.model.ts` |
| Permission Check | Middleware guard | `src/middleware/roles.ts` |

### Error Handling Patterns

| Error Type | HTTP Code | Response Format | File Path |
|------------|-----------|-----------------|-----------|
| Validation Error | 400 | `{ error: "message", details: [] }` | `src/middleware/validate.ts` |
| Unauthorized | 401 | `{ error: "Unauthorized" }` | `src/middleware/auth.ts` |
| Forbidden | 403 | `{ error: "Forbidden" }` | `src/middleware/roles.ts` |
| Not Found | 404 | `{ error: "Resource not found" }` | `src/middleware/error.ts` |
| Server Error | 500 | `{ error: "Internal server error" }` | `src/middleware/error.ts` |

## Grep Commands

```bash
# Find all environment variable usage
grep -rE "process\.env\.|os\.environ|os\.getenv" --include="*.ts" --include="*.js" --include="*.py" | sort -u

# Find .env.example
find . -name ".env.example" -o -name ".env.sample" -o -name "*.env.example"

# Find config files
find . -name "config.*" -o -name "settings.py" -o -name ".env*"

# Find package.json scripts
cat package.json | grep -A20 '"scripts"'

# Find startup files
find . -name "index.ts" -o -name "main.ts" -o -name "app.ts" -o -name "server.ts"

# Find Docker startup
cat docker-compose.yml | grep -A5 "command:"

# Find authentication middleware
grep -rE "authMiddleware|auth\.middleware|@UseGuards|login_required" --include="*.ts" --include="*.js" --include="*.py"

# Find error handlers
grep -rE "errorHandler|error\.middleware|@Catch|exception" --include="*.ts" --include="*.js" --include="*.py"
```

## Self-Check

- [ ] All environment variables documented
- [ ] Prerequisites listed with versions
- [ ] Startup sequence documented
- [ ] Core user flow traced with file paths
- [ ] Authentication model documented
- [ ] Authorization/permissions documented
- [ ] Error handling patterns documented
- [ ] All referenced files exist

## Detection Patterns by Script

### environment_analyzer.py

**Environment Variable Sources:**
| Source | Pattern | Example |
|--------|---------|---------|
| .env.example | `VAR_NAME=value` | `DATABASE_URL=postgresql://...` |
| Pydantic Settings | `class Settings(BaseSettings)` | `JWT_SECRET_KEY: str` |
| Python code | `os.environ.get('VAR')` | `os.getenv('DATABASE_URL')` |
| Node.js code | `process.env.VAR` | `process.env.NODE_ENV` |

**Startup Detection:**
- Docker: `docker-compose.yml` exists
- Python: `requirements.txt`, `pyproject.toml`, `main.py`
- Node.js: `package.json` scripts (`dev`, `start`)

### auth_analyzer.py

**Authentication Types Detected:**
| Type | Indicators |
|------|------------|
| JWT Bearer | `Authorization: Bearer`, `jwt.encode()`, `jwt.verify()` |
| JWT Cookie | `response.set_cookie()`, `httponly=True` + JWT patterns |
| Session | `req.session`, `express-session`, `flask_session` |
| OAuth | `passport.authenticate`, `authlib`, `next-auth` |
| API Key | `x-api-key`, `api_key` parameter |

**RBAC Detection:**
- Role checks: `is_admin`, `role == 'admin'`, `has_role()`
- Permission checks: `has_permission()`, `@permission_required`

### happy_path_tracer.py

**Flow Types Traced:**
| Flow | Entry Points | Traces Through |
|------|--------------|----------------|
| Login | `/login` route | Form -> API -> Auth Service -> Token Store |
| CRUD | List/Create routes | Route -> Handler -> Service -> Database |

**Component Types:**
- `UI` - React components, pages, forms
- `API_Client` - API client functions, fetch calls
- `Route` - API route definitions
- `Service` - Business logic functions
- `Repository` - Database operations

### error_handler_analyzer.py

**Exception Detection:**
| Language | Pattern |
|----------|---------|
| Python | `class CustomError(Exception):` |
| TypeScript | `class CustomError extends Error` |

**Validation Libraries:**
| Library | Detection |
|---------|-----------|
| Pydantic | `from pydantic import`, `BaseModel` |
| Zod | `from 'zod'` |
| Joi | `from 'joi'` |
| class-validator | `@IsString`, `@IsEmail` |

**Error Response Format:**
Common fields: `error`, `message`, `details`, `code`

## Example Output

Running all scripts on a project produces:

```bash
# Generate complete Phase 7 documentation
python scripts/environment_analyzer.py /path/to/project --format markdown > phase-7-env.md
python scripts/auth_analyzer.py /path/to/project --format markdown > phase-7-auth.md
python scripts/happy_path_tracer.py /path/to/project --format markdown > phase-7-flows.md
python scripts/error_handler_analyzer.py /path/to/project --format markdown > phase-7-errors.md
```

