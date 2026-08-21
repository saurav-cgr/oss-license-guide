# oss-license-guide

Open Source License Information Assistant — educational tool that explains likely
software-license obligations under stated scenarios. Not legal advice.

Status: **Milestone 0 scaffold** (project setup, health check, Docker deployment).

## Stack

- Frontend: React + TypeScript (Vite), served by nginx
- Backend: FastAPI + Python (uv), Uvicorn
- Deployment: Docker Compose (`web` on `:8080`, `api` on `:8000`)

## Run locally

```bash
docker compose up --build
# Open http://localhost:8080
```

## Development

Backend:

```bash
cd backend
uv sync --dev
uv run pytest
uv run ruff check src tests
```

Frontend:

```bash
cd frontend
npm install
npm run typecheck
npm test
npm run lint
npm run build
```
