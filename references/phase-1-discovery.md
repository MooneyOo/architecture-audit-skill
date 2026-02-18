# Phase 1: Discovery & Stack Detection

## Overview

Auto-detect the technology stack by scanning configuration files and project structure. Build a complete technology manifest.

## Actions

1. Scan project root for configuration files
2. Read package managers and dependency files
3. Identify languages, frameworks, databases
4. Detect infrastructure patterns
5. Record project directory tree (top 3 levels)

## Files to Scan

| File | What It Reveals |
|------|-----------------|
| `package.json` | Node.js, npm packages, scripts |
| `yarn.lock` / `pnpm-lock.yaml` | Package manager |
| `requirements.txt` | Python dependencies |
| `Pipfile` | Python + pipenv |
| `pyproject.toml` | Python + poetry/setuptools |
| `go.mod` | Go modules |
| `Cargo.toml` | Rust crates |
| `composer.json` | PHP dependencies |
| `Gemfile` | Ruby gems |
| `pom.xml` / `build.gradle` | Java/Kotlin |
| `docker-compose.yml` | Services, databases, infrastructure |
| `Dockerfile` | Runtime environment |
| `.github/workflows/*.yml` | CI/CD, deployment |
| `vercel.json` / `netlify.toml` | Deployment platform |
| `terraform/` | Infrastructure as code |
| `.env.example` | Environment variables |

## Patterns to Detect

### Languages
```
package.json     → JavaScript/TypeScript
requirements.txt → Python
go.mod           → Go
Cargo.toml       → Rust
pom.xml          → Java
composer.json    → PHP
Gemfile          → Ruby
```

### Frameworks
```
"next"           → Next.js
"express"        → Express.js
"fastapi"        → FastAPI
"django"         → Django
"flask"          → Flask
"spring-boot"    → Spring Boot
"rails"          → Ruby on Rails
"laravel"        → Laravel
"react"          → React
"vue"            → Vue.js
"angular"        → Angular
"svelte"         → Svelte
```

### Databases
```
"pg" / "postgres" / "psql"  → PostgreSQL
"mysql" / "mysql2"          → MySQL
"mongodb" / "mongoose"      → MongoDB
"redis" / "ioredis"         → Redis
"sqlite"                    → SQLite
"prisma"                    → Prisma ORM
"sequelize"                 → Sequelize ORM
"typeorm"                   → TypeORM
"sqlalchemy"                → SQLAlchemy
```

### Message Brokers / Queues
```
"amqplib" / "rabbitmq"      → RabbitMQ
"kafkajs" / "kafka-python"  → Kafka
"bull" / "bee-queue"        → Redis queues
"celery"                    → Celery (Python)
```

### Infrastructure Patterns
```
docker-compose.yml with multiple services → Microservices
single Dockerfile                          → Monolith
serverless.yml / SAM template              → Serverless
kubernetes/ / k8s/                         → Kubernetes
```

## Output Section

Populates: `## 1. Project Overview & Technology Stack`

### Technology Manifest Table
| Category | Technology | Version | Source |
|----------|------------|---------|--------|
| Language | [DETECTED] | [VERSION] | [FILE] |
| Framework | [DETECTED] | [VERSION] | [FILE] |
| Database | [DETECTED] | [VERSION] | [FILE] |

### Directory Tree
Generate with:
```bash
tree -L 3 -I 'node_modules|.git|__pycache__|venv|dist|build'
```

## Grep Commands

```bash
# Find package manager
ls package.json requirements.txt go.mod Cargo.toml pyproject.toml 2>/dev/null

# Detect frameworks in package.json
grep -E '"(next|express|react|vue|angular|svelte|fastapi|django|flask)"' package.json

# Detect databases
grep -rE '(postgres|mysql|mongodb|redis|sqlite|mongoose|prisma|sequelize)' --include="*.json" --include="*.txt" --include="*.toml"

# Find environment variables
find . -name ".env.example" -o -name ".env.sample" -o -name "*.env.example"
```

## Third-Party Services

### Payment Processors
```
"stripe"         → Stripe
"paypal"         → PayPal
"braintree"      → Braintree
"square"         → Square
```

### Cloud Providers
```
"aws-sdk" / "boto3"           → AWS
"@google-cloud" / "gcloud"    → Google Cloud
"azure" / "@azure"            → Microsoft Azure
```

### Authentication
```
"auth0"          → Auth0
"firebase"       → Firebase Auth
"passport"       → Passport.js
"next-auth"      → NextAuth.js
"cognito"        → AWS Cognito
"python-jose"    → JWT (Python)
```

### Communication
```
"sendgrid"       → SendGrid Email
"mailgun"        → Mailgun
"twilio"         → Twilio SMS/Voice
"socket.io"      → WebSocket
```

### Monitoring & Logging
```
"sentry"         → Sentry Error Tracking
"datadog"        → Datadog Monitoring
"newrelic"       → New Relic APM
"winston"        → Winston Logger (Node.js)
"pino"           → Pino Logger (Node.js)
"logging"        → Python Logging
```

### HTTP Clients
```
"axios"          → Axios
"httpx"          → HTTPX (Python)
"requests"       → Requests (Python)
"node-fetch"     → Node Fetch
"got"            → Got (Node.js)
```

## Technology Categorization

When analyzing dependencies, categorize each into one of these types:

| Category | Examples | Purpose |
|----------|----------|---------|
| `language` | python, node, go | Runtime environment |
| `framework` | react, fastapi, django | Application framework |
| `database` | postgresql, mongodb | Data storage |
| `orm` | sqlalchemy, prisma, typeorm | Database abstraction |
| `cache` | redis, memcached | Caching layer |
| `queue` | rabbitmq, kafka, celery | Message queue |
| `testing` | pytest, jest, vitest | Test framework |
| `service` | stripe, sendgrid, aws | Third-party service |
| `utility` | lodash, date-fns | Helper libraries |
| `dev-tool` | eslint, ruff, mypy | Development tools |

## Example Output

### Technology Manifest (Fullstack Project)

```markdown
## 1. Project Overview & Technology Stack

### 1.1 Technology Manifest

| Category | Technology | Version | Source |
|----------|------------|---------|--------|
| Language | Python | 3.11+ | backend/requirements.txt |
| Language | TypeScript | 5.3.x | frontend/package.json |
| Framework (Backend) | FastAPI | 0.109+ | backend/requirements.txt |
| Framework (Frontend) | React | 18.2.x | frontend/package.json |
| Build Tool | Vite | 5.0.x | frontend/package.json |
| State Management | Zustand | 4.4.x | frontend/package.json |
| Database | PostgreSQL | - | docker-compose.yml |
| ORM | SQLAlchemy | 2.0+ | backend/requirements.txt |
| Migrations | Alembic | 1.13+ | backend/requirements.txt |
| HTTP Client | HTTPX | 0.26+ | backend/requirements.txt |
| Testing (Backend) | pytest | 8.0+ | backend/requirements.txt |
| Testing (Frontend) | Vitest | 1.2+ | frontend/package.json |
| E2E Testing | Playwright | 1.48+ | frontend/package.json |

### 1.2 Project Structure

```
project-root/
├── backend/
│   ├── src/
│   │   ├── api/
│   │   ├── models/
│   │   ├── services/
│   │   └── core/
│   ├── tests/
│   ├── alembic/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── stores/
│   ├── e2e/
│   └── package.json
├── docker-compose.yml
└── README.md
```

### 1.3 Infrastructure

| Component | Technology | Notes |
|-----------|------------|-------|
| Containerization | Docker | Multi-container setup |
| Backend Server | Uvicorn | ASGI server |
| Frontend Server | Vite Dev Server | Development |
| Database | PostgreSQL | Primary data store |
```

## Dependency Analysis Script

Use the provided script to automate dependency analysis:

```bash
# Analyze a project directory
python scripts/analyze_dependencies.py /path/to/project --format json

# Output as markdown
python scripts/analyze_dependencies.py /path/to/project --format markdown

# Exclude dev dependencies
python scripts/analyze_dependencies.py /path/to/project --no-dev
```

## Self-Check

- [ ] Language(s) identified with versions
- [ ] Framework(s) identified with versions
- [ ] Database(s) identified
- [ ] ORM/ODM libraries listed
- [ ] Third-party services detected
- [ ] Infrastructure pattern determined
- [ ] Directory tree generated (3 levels)
- [ ] All source files referenced in table exist
- [ ] Technology manifest table complete
- [ ] Dependencies categorized by type
