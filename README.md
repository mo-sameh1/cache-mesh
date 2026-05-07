# CacheMesh Project Scaffold

This repository is the first scaffolding pass for the CacheMesh distributed semantic cache project. It gives the team a shared Python environment, a placeholder service layout, environment configuration, Docker files, and stub APIs that reflect the architecture. It does **not** implement real distributed behavior yet.

## What this phase includes

- Built-in Python `venv` workflow for teammate-friendly onboarding
- One `requirements.txt` for the initial dependency set
- Root `.env.example` plus a local `.env`
- Placeholder FastAPI services for the gateway, name service, replica service, and inference adapter
- A static UI placeholder under `apps/ui/`
- A generic `Dockerfile` and an initial `docker-compose.yml`
- Smoke tests for config loading, app creation, imports, and placeholder routes

## What this phase does not include

- Real cache read or write logic
- Real membership tracking
- Real Lamport or token-based synchronization
- Real Qdrant integration beyond placeholder wiring
- Real fault detection or recovery behavior

## Quick start on Windows

1. Install Python 3.13.
2. Install Docker Desktop and make sure `docker compose` works in PowerShell.
3. Clone the repo and open PowerShell in the repo root.
4. Create the virtual environment:

```powershell
py -3.13 -m venv .venv
```

5. Activate the virtual environment:

```powershell
.venv\Scripts\Activate.ps1
```

6. Install Python dependencies:

```powershell
pip install -r requirements.txt
```

7. Copy the example environment file if you are starting from a fresh clone:

```powershell
Copy-Item .env.example .env
```

8. Start the initial container topology:

```powershell
docker compose up -d
```

9. Run the scaffold test suite:

```powershell
pytest
```

## Quick start on macOS or Linux

Use the same overall flow, but activate the environment with:

```bash
source .venv/bin/activate
```

## Repo map

- `apps/ui/`
  Static UI placeholder and notes for the future fault toggle / metrics dashboard.
- `services/gateway/`
  Placeholder API gateway entrypoint, routes, config wrapper, and service layer.
- `services/name_service/`
  Placeholder membership and heartbeat service.
- `services/replica/`
  Placeholder replica API, cache service, sync service, fault service, and vector store adapter.
- `services/inference_adapter/`
  Placeholder inference API and stub client for miss-path integration.
- `shared/`
  Common config, models, constants, protocol helpers, logging setup, Lamport clock placeholder, and fault control helpers.
- `tests/`
  Import smoke tests, config tests, app creation tests, and placeholder route tests.

## Local development notes

Each service currently exposes a health endpoint and placeholder routes that return stub payloads. This lets the team start building against stable request and response shapes before the real implementation lands.

Example local runs:

```powershell
uvicorn services.gateway.main:app --reload --host 0.0.0.0 --port 8000
uvicorn services.replica.main:app --reload --host 0.0.0.0 --port 8201
```

## Docker notes

- The root `Dockerfile` is generic for Python services.
- The root `docker-compose.yml` is a **topology scaffold**, not the final deployment system.
- Replica services are configured as separate containers with per-service environment overrides.
- Qdrant is provisioned as one local instance per replica using named volumes.


