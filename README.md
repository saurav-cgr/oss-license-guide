# oss-license-guide

Open Source License Information Assistant — an educational tool that explains
likely software-license obligations under stated scenarios. It is **not** legal
advice, and its rules have **not** been independently or professionally
reviewed.

Status: **Milestone 8 — portable MVP release** (deterministic analysis, source
citations, optional model explanation, Docker deployment).

## What it does

Enter an exact SPDX license expression and a software-use scenario. The
deterministic core parses the expression, detects missing facts, applies
versioned maintainer-reviewed rules for `MIT`, `Apache-2.0`, and
`MIT OR Apache-2.0`, and returns a structured, source-backed answer with
claim-level citations. Unsupported or incomplete scenarios abstain rather than
guess.

An optional model explanation (Gemini or an OpenAI-compatible provider) explains
the structured findings. Provider failure always degrades to the deterministic,
citation-backed result.

## Stack

- Frontend: React + TypeScript (Vite), served by a non-root nginx.
- Backend: FastAPI + Python (uv), Uvicorn, runs as a non-root user.
- Deployment: Docker Compose. Only the **web** container is published
  (`:8080`); the API is reachable only through the web reverse proxy.

## Run locally

```bash
docker compose up --build
# Open http://localhost:8080
```

The API is not published to the host. All `/api/*` traffic goes through the web
reverse proxy.

## Configuration

Copy `.env.example` to `.env` for local overrides (never commit `.env`):

- `OLG_CORS_ORIGINS` — allowed CORS origins.
- `OLG_PROVIDERS_ENABLED` — provider allowlist (`gemini,openai`).
- `OLG_GEMINI_ENDPOINT` / `OLG_OPENAI_ENDPOINT` — server-controlled endpoints.
- `OLG_GEMINI_API_KEY` — development-only key; never enable
  `OLG_ALLOW_DEV_PROVIDER_KEY` on a public deployment.

Provider keys supplied by users travel only in request headers, are held in
memory, and are never stored. See `PRIVACY.md`.

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

## Testing

- Backend integration tests (incl. provider boundary and the 60-case golden
  safety suite) run through the FastAPI boundary and are offline.
- Frontend integration tests render complete user flows against a controlled
  API boundary.
- Deployment smoke test:

```bash
scripts/smoke-test.sh
```

This builds the images, launches the stack, verifies frontend delivery, `/api`
routing, a complete deterministic analysis, no secret leakage, and that only the
web endpoint is exposed publicly.

Container checks:

```bash
docker compose config --quiet           # validate the compose file
docker build --check backend frontend   # static Dockerfile checks
# Dependency / vulnerability scan (one of):
#   docker scout cves oss-license-guide-api oss-license-guide-web   # requires docker login
#   trivy image oss-license-guide-api oss-license-guide-web
```

## Security

- Multi-stage images with no build tooling or development secrets at runtime.
- Backend and web containers run as non-root users.
- Model-provider endpoints are server-controlled and allowlisted; arbitrary
  base URLs are rejected.
- No accounts, no saved history, no database in the request path.

## Privacy

See `PRIVACY.md` for what the application does and does not retain.

## Project layout

- `frontend/` — React application and nginx configuration.
- `backend/` — FastAPI package, bundled SPDX catalog, rules, and golden cases.
- `compose.yaml` — reference deployment.
- `docs/plan/` — product, scope, architecture, and implementation documents.
