# CacheMesh Project Scaffold

This repository scaffolds the CacheMesh distributed semantic cache project. It includes FastAPI services for the gateway, name service, replica node, and inference adapter, plus Qdrant-backed replica storage and a Docker setup that can be split across multiple LAN machines.

## What this phase includes

- One Python environment for the whole repo
- FastAPI services for `gateway`, `name-service`, `replica`, and `inference-adapter`
- Shared config, protocol models, and client helpers
- Replica membership registration and heartbeat tracking
- Replica-to-replica distributed write coordination
- A Docker Compose setup for running only the services assigned to the current machine

## What this phase does not include

- Persistent shared state for the name service
- Automatic service discovery beyond the configured name service and replica target lists
- A full production orchestrator such as Kubernetes or Swarm

## Local Python setup

### Windows

1. Install Python 3.13.
2. Clone the repo and open PowerShell in the repo root.
3. Create the virtual environment:

```powershell
py -3.13 -m venv .venv
```

4. Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

5. Install dependencies:

```powershell
pip install -r requirements.txt
```

6. Copy the environment template:

```powershell
Copy-Item .env.example .env
```

### macOS / Linux

Use the same flow, but activate the environment with:

```bash
source .venv/bin/activate
```

## Docker deployment model

The root `docker-compose.yml` now describes a single machine in the distributed system. Each machine runs the same Compose file, but chooses its local services through `COMPOSE_PROFILES` in `.env`.

Available profiles:

- `name-service`
- `gateway`
- `inference`
- `replica`

The `replica` profile also starts a local `qdrant` container automatically.

### Standard startup flow on any machine

1. Copy `.env.example` to `.env`.
2. Set the machine-specific values in `.env`.
3. Start the assigned services:

```powershell
docker compose up -d --build
```

4. Check status:

```powershell
docker compose ps
```

5. Check logs when needed:

```powershell
docker compose logs -f
```

### Required `.env` values

These values drive the distributed deployment:

- `COMPOSE_PROFILES`
- `NAME_SERVICE_URL`
- `INFERENCE_ADAPTER_URL`
- `GATEWAY_REPLICA_TARGETS`
- `GATEWAY_REPLICA_URLS`
- `REPLICA_ID`
- `REPLICA_PORT`
- `REPLICA_ADVERTISED_HOST`
- `REPLICA_ADVERTISED_PORT`
- `REPLICA_PEER_TARGETS`
- `INITIAL_TOKEN_REPLICA_ID`
- `QDRANT_URL`
- `QDRANT_HOST_PORT`

### Example three-machine layout

Example mapping:

- `192.168.116.204`: `name-service` + `replica-a`
- `192.168.116.206`: `inference-adapter` + `replica-b`
- `192.168.116.207`: `gateway` + `replica-c`

Machine `192.168.116.204`:

```env
COMPOSE_PROFILES=name-service,replica
NAME_SERVICE_URL=http://192.168.116.204:8100
INFERENCE_ADAPTER_URL=http://192.168.116.206:8050
GATEWAY_REPLICA_TARGETS=replica-a=http://192.168.116.204:8201,replica-b=http://192.168.116.206:8202,replica-c=http://192.168.116.207:8203
GATEWAY_REPLICA_URLS=http://192.168.116.204:8201,http://192.168.116.206:8202,http://192.168.116.207:8203
REPLICA_ID=replica-a
REPLICA_PORT=8201
REPLICA_ADVERTISED_HOST=192.168.116.204
REPLICA_ADVERTISED_PORT=8201
REPLICA_PEER_TARGETS=replica-a=http://192.168.116.204:8201,replica-b=http://192.168.116.206:8202,replica-c=http://192.168.116.207:8203
INITIAL_TOKEN_REPLICA_ID=replica-a
QDRANT_URL=http://qdrant:6333
QDRANT_HOST_PORT=6334
```

Machine `192.168.116.206`:

```env
COMPOSE_PROFILES=inference,replica
NAME_SERVICE_URL=http://192.168.116.204:8100
INFERENCE_ADAPTER_URL=http://192.168.116.206:8050
GATEWAY_REPLICA_TARGETS=replica-a=http://192.168.116.204:8201,replica-b=http://192.168.116.206:8202,replica-c=http://192.168.116.207:8203
GATEWAY_REPLICA_URLS=http://192.168.116.204:8201,http://192.168.116.206:8202,http://192.168.116.207:8203
REPLICA_ID=replica-b
REPLICA_PORT=8202
REPLICA_ADVERTISED_HOST=192.168.116.206
REPLICA_ADVERTISED_PORT=8202
REPLICA_PEER_TARGETS=replica-a=http://192.168.116.204:8201,replica-b=http://192.168.116.206:8202,replica-c=http://192.168.116.207:8203
INITIAL_TOKEN_REPLICA_ID=replica-a
QDRANT_URL=http://qdrant:6333
QDRANT_HOST_PORT=6335
INFERENCE_BACKEND=hf_transformers
INFERENCE_DEVICE=auto
```

Machine `192.168.116.207`:

```env
COMPOSE_PROFILES=gateway,replica
NAME_SERVICE_URL=http://192.168.116.204:8100
INFERENCE_ADAPTER_URL=http://192.168.116.206:8050
GATEWAY_REPLICA_TARGETS=replica-a=http://192.168.116.204:8201,replica-b=http://192.168.116.206:8202,replica-c=http://192.168.116.207:8203
GATEWAY_REPLICA_URLS=http://192.168.116.204:8201,http://192.168.116.206:8202,http://192.168.116.207:8203
REPLICA_ID=replica-c
REPLICA_PORT=8203
REPLICA_ADVERTISED_HOST=192.168.116.207
REPLICA_ADVERTISED_PORT=8203
REPLICA_PEER_TARGETS=replica-a=http://192.168.116.204:8201,replica-b=http://192.168.116.206:8202,replica-c=http://192.168.116.207:8203
INITIAL_TOKEN_REPLICA_ID=replica-a
QDRANT_URL=http://qdrant:6333
QDRANT_HOST_PORT=6336
```

After saving `.env` on each machine, start that machine with:

```powershell
docker compose up -d --build
```

### Firewall ports

Open these inbound ports on the matching machine:

- `8100` on the name service machine
- `8050` on the inference machine
- `8000` on the gateway machine
- `8201`, `8202`, `8203` on the three replica machines

### Verification

Check the key endpoints from any machine:

```powershell
curl.exe http://192.168.116.204:8100/health
curl.exe http://192.168.116.204:8100/members
curl.exe http://192.168.116.206:8050/health
curl.exe http://192.168.116.207:8000/health
curl.exe http://192.168.116.204:8201/health
curl.exe http://192.168.116.206:8202/health
curl.exe http://192.168.116.207:8203/health
```

The `/members` response should show all three replicas once they are registered.

## Local development notes

You can still run services directly without Docker:

```powershell
uvicorn services.gateway.main:app --reload --host 0.0.0.0 --port 8000
uvicorn services.replica.main:app --reload --host 0.0.0.0 --port 8201
```

## Tests

Run the test suite with:

```powershell
pytest
```

## Repo map

- `apps/ui/`
  Static UI placeholder and notes for the future dashboard.
- `services/gateway/`
  Gateway entrypoint, routes, config wrapper, and service layer.
- `services/name_service/`
  Membership and heartbeat service.
- `services/replica/`
  Replica API, cache service, sync service, fault service, and vector store adapter.
- `services/inference_adapter/`
  Inference API and runtime selection.
- `shared/`
  Common config, models, logging setup, protocol helpers, clock logic, and shared HTTP client code.
- `tests/`
  Unit and integration coverage for config, services, liveness, gateway flows, and replica coordination.
