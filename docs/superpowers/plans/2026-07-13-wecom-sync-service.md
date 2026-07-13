# WeCom Sync Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable v1 Enterprise WeChat conversation archive service and visual admin workspace under `app/weCom/`.

**Architecture:** The project is a self-contained Docker Compose app with FastAPI API, a DB-cursor worker, MySQL, a React/Vite frontend, and a Python CLI. Real Enterprise WeChat SDK operations are isolated behind adapters so the app can run with deterministic stubs until secrets, private key, and Linux SDK are supplied.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pytest, Typer, MySQL 8.4, React, Vite, TypeScript, Vitest, CSS modules/plain CSS.

---

## File Structure

- `app/weCom/backend/wecom_app/`: FastAPI app, settings, auth, DB models, schemas, API routers, service layer, worker tasks, Enterprise WeChat adapters, and CLI.
- `app/weCom/backend/tests/`: Pytest suite for auth, API contracts, transform behavior, CLI, and worker stubs.
- `app/weCom/frontend/src/`: React workspace UI, API client, mock fallback data, reusable modules, and styles derived from the demo.
- `app/weCom/frontend/src/**/*.test.tsx`: Vitest tests for UI state and data transforms.
- `app/weCom/docker-compose.yml`: API, worker, frontend, and MySQL local deployment.
- `app/weCom/README.md`: Project overview, do/don't boundaries, deployment, secrets, variables, and CLI usage.

## Tasks

### Task 1: Backend Scaffold And Health

**Files:**
- Create: `app/weCom/backend/pyproject.toml`
- Create: `app/weCom/backend/wecom_app/main.py`
- Create: `app/weCom/backend/wecom_app/core/config.py`
- Create: `app/weCom/backend/wecom_app/api/health.py`
- Test: `app/weCom/backend/tests/test_health.py`

- [ ] Write failing health tests for `GET /health` returning app status and configured environment.
- [ ] Run: `cd app/weCom/backend && pytest tests/test_health.py -q`; expected failure because app files do not exist.
- [ ] Implement FastAPI app, Pydantic settings, and health router.
- [ ] Run: `cd app/weCom/backend && pytest tests/test_health.py -q`; expected pass.

### Task 2: Database Schema And Alembic

**Files:**
- Create: `app/weCom/backend/wecom_app/db/base.py`
- Create: `app/weCom/backend/wecom_app/db/session.py`
- Create: `app/weCom/backend/wecom_app/models/*.py`
- Create: `app/weCom/backend/alembic/env.py`
- Create: `app/weCom/backend/alembic/versions/20260713_0001_initial_schema.py`
- Test: `app/weCom/backend/tests/test_models.py`

- [ ] Write tests that assert required tables and key columns from `Tech_weCom_sync_service.md` exist in SQLAlchemy metadata.
- [ ] Run the model test and confirm it fails before models exist.
- [ ] Implement Raw, Control, and Business SQLAlchemy models with latest storage fields (`storage_backend`, `storage_bucket`, `storage_key`, `storage_url`) and `is_supported`.
- [ ] Implement Alembic migration for MySQL-compatible schema and indexes.
- [ ] Run model tests and an SQLite metadata create smoke test.

### Task 3: Auth And Frontend API Contracts

**Files:**
- Create: `app/weCom/backend/wecom_app/api/deps.py`
- Create: `app/weCom/backend/wecom_app/api/observable.py`
- Create: `app/weCom/backend/wecom_app/api/conversations.py`
- Create: `app/weCom/backend/wecom_app/api/attachments.py`
- Create: `app/weCom/backend/wecom_app/schemas/archive.py`
- Test: `app/weCom/backend/tests/test_archive_api.py`

- [ ] Write failing API tests for bearer token rejection, observable employee listing, conversation listing, message listing, current conversation search, and attachment status errors.
- [ ] Run targeted tests and confirm they fail because routes are missing.
- [ ] Implement route contracts from section 12 of `Tech_weCom_sync_service.md` using SQLAlchemy queries and deterministic seeded test fixtures.
- [ ] Run targeted API tests and confirm pass.

### Task 4: Callback And WeCom Adapter Stubs

**Files:**
- Create: `app/weCom/backend/wecom_app/wecom/callback_crypto.py`
- Create: `app/weCom/backend/wecom_app/wecom/client.py`
- Create: `app/weCom/backend/wecom_app/api/callbacks.py`
- Test: `app/weCom/backend/tests/test_callbacks.py`

- [ ] Write failing tests for all callback URL verification paths and POST event persistence.
- [ ] Implement a crypto interface that validates config shape and provides a deterministic local stub when real callback secrets are not configured.
- [ ] Implement callback routes that persist `raw_event` quickly and never run long sync work inline.
- [ ] Run callback tests.

### Task 5: Worker Tasks And Message Transform

**Files:**
- Create: `app/weCom/backend/wecom_app/worker.py`
- Create: `app/weCom/backend/wecom_app/services/transform.py`
- Create: `app/weCom/backend/wecom_app/services/attachments.py`
- Create: `app/weCom/backend/wecom_app/services/sync_jobs.py`
- Test: `app/weCom/backend/tests/test_transform.py`
- Test: `app/weCom/backend/tests/test_worker.py`

- [ ] Write failing tests for text, image, link, agree/disagree, recall, and unsupported message transforms.
- [ ] Implement minimal transform logic, including unsupported business placeholders and recall updates.
- [ ] Write failing tests for worker cursor reads and stub sync once behavior.
- [ ] Implement DB cursor task loop primitives and one-shot task entrypoints.
- [ ] Run transform and worker tests.

### Task 6: CLI

**Files:**
- Create: `app/weCom/backend/wecom_app/cli.py`
- Test: `app/weCom/backend/tests/test_cli.py`

- [ ] Write failing Typer CLI tests for `callback urls`, `health`, and `sync once --type message`.
- [ ] Implement `wecomctl` commands with clear output and non-zero exit codes for invalid configuration.
- [ ] Run CLI tests.

### Task 7: Frontend Workspace

**Files:**
- Create: `app/weCom/frontend/package.json`
- Create: `app/weCom/frontend/vite.config.ts`
- Create: `app/weCom/frontend/src/App.tsx`
- Create: `app/weCom/frontend/src/api/client.ts`
- Create: `app/weCom/frontend/src/components/*.tsx`
- Create: `app/weCom/frontend/src/styles.css`
- Test: `app/weCom/frontend/src/App.test.tsx`

- [ ] Write failing Vitest tests for employee selection, conversation filtering, unsupported message rendering, recall rendering, search drawer, and detail drawer switching.
- [ ] Implement React UI using the demo tokens and layout, with mock fallback data when API is unavailable.
- [ ] Run frontend tests.
- [ ] Run a production build.

### Task 8: Docker, README, And Verification

**Files:**
- Create: `app/weCom/Dockerfile.api`
- Create: `app/weCom/Dockerfile.frontend`
- Create: `app/weCom/docker-compose.yml`
- Create: `app/weCom/.env.example`
- Create: `app/weCom/README.md`

- [ ] Add Dockerfiles and Compose services for API, worker, frontend, and MySQL.
- [ ] Add `.env.example` with every variable from the tech spec and comments for current missing secret/SDK setup.
- [ ] Write README with project introduction, basic capabilities, boundaries, deployment, secret configuration, SDK/private-key mounts, and CLI examples.
- [ ] Run backend lint/tests, frontend lint/tests/build, and available Docker config validation.

## Self-Review

- Spec coverage: the plan covers API/Worker split, MySQL schema, Alembic, callback routes, local attachment proxy, fixed admin token auth, CLI, frontend workspace modules, Docker Compose, and README.
- Known v1 stub: real Linux SDK decrypt/pull is adapter-backed and documented as pending actual SDK, private key, and secret configuration.
- Historical document resolution: unsupported messages follow `Tech_weCom_sync_service.md` and become business placeholders.
