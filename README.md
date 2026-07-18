# ⚒ ForgeBoard

**Shopify for AI agents** — connect tools, describe a goal, deploy an agent, watch it run.

---

## Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python 3.11+), async |
| Database | PostgreSQL 16 + SQLAlchemy 2 + Alembic |
| Queue / scheduler | Redis 7 + Celery 5 |
| AI provider | Anthropic (Claude) — single provider for MVP |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Auth | JWT (access + refresh) + bcrypt |
| Secret encryption | Fernet (MVP) — upgrade to Vault/KMS before production |

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose v2)
- Git

For local development without Docker you also need:
- Python 3.11+
- Node.js 20+

---

## Quick start (Docker Compose)

```bash
# 1. Clone the repo
git clone <repo-url> forgeboard
cd forgeboard

# 2. Create your .env from the example
cp .env.example .env
# Edit .env — at minimum set:
#   SECRET_KEY, JWT_SECRET_KEY, ANTHROPIC_API_KEY, FERNET_KEY

# 3. Generate required secret values
python -c "import secrets; print(secrets.token_hex(32))"   # SECRET_KEY + JWT_SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # FERNET_KEY

# 4. Boot everything
docker compose up --build

# Services:
#   Backend API  →  http://localhost:8000
#   API docs     →  http://localhost:8000/docs
#   Frontend     →  http://localhost:3000
#   Postgres     →  localhost:5432
#   Redis        →  localhost:6379
```

---

## Local development (without Docker)

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload --port 8000

# Start Celery worker (separate terminal)
celery -A app.workers.celery_app worker --loglevel=info

# Start Celery Beat scheduler (separate terminal)
celery -A app.workers.celery_app beat --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # → http://localhost:5173
```

---

## Database migrations

```bash
cd backend

# Generate a new migration after changing models
alembic revision --autogenerate -m "describe the change"

# Apply pending migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1
```

---

## Project structure

```
forgeboard/
├── backend/
│   ├── alembic/              # DB migration scripts
│   ├── app/
│   │   ├── api/v1/           # Route handlers (endpoints/)
│   │   ├── core/             # Config, DB engine, security utils
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/         # Business logic layer
│   │   └── workers/          # Celery app + tasks
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/       # Shared UI components
│   │   ├── lib/              # API client, utilities
│   │   ├── pages/            # Route-level page components
│   │   └── store/            # Zustand state (auth, etc.)
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Build phases

| Phase | Description | Status |
|---|---|---|
| 0 | Project scaffolding | ✅ Complete |
| 1 | Auth & workspace | ✅ Complete |
| 2 | Connector layer | — |
| 3 | Agent builder | — |
| 4 | Orchestration engine | — |
| 5 | Kanban operations board | — |
| 6 | Governance basics | — |
| 7 | Polish & demo readiness | — |

---

## Production notes (deferred items)

These shortcuts are intentional for MVP and **must be addressed before real paying customers**:

- **Fernet encryption** (`FERNET_KEY` in `.env`) → upgrade to HashiCorp Vault or AWS Secrets Manager
- **Single Anthropic provider** → abstract model provider layer when BYOK/multi-model is needed
- **JWT in localStorage** (via Zustand persist) → consider HttpOnly cookies for production
- **Docker Compose** → Kubernetes / managed container platform for scaling
- **No billing metering** → integrate Stripe + usage tracking before monetizing
- **Single-tenant** → workspace isolation / multi-tenant when onboarding teams
