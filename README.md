# CacheMesh

CacheMesh is a distributed semantic cache for LLM responses. It is built as a three-machine system with:

- a `name-service` for replica discovery and liveness
- an `inference-adapter` that runs the language model
- a `gateway` that accepts client requests
- three `replica` nodes, each backed by its own local Qdrant store

The project also includes a browser UI in [apps/ui](apps/ui/) for health checks, query flow demos, direct replica reads, coordination visibility, and fault injection.

## Architecture

Request flow:

1. Client sends a prompt to the `gateway`
2. `gateway` asks `name-service` for healthy replicas
3. `gateway` reads from one replica
4. On cache hit, the cached response is returned
5. On cache miss, `gateway` calls `inference-adapter`
6. The selected replica stores the response and replicates it to peers

Distributed behavior included in the codebase:

- token-based distributed write coordination across replicas
- replica registration and heartbeat liveness
- automatic late-join bootstrap sync from a healthy peer
- automatic recovery sync after a faulted replica becomes healthy again
- replica eviction from `name-service` after one hour offline

## Repository Layout

- `apps/ui/` static demo console
- `services/gateway/` gateway API and routing logic
- `services/name_service/` membership and liveness service
- `services/replica/` cache, replication, coordination, fault, and sync logic
- `services/inference_adapter/` LLM adapter and runtime loading
- `shared/` common config, models, clocks, logging, and HTTP helpers
- `tests/` unit and integration coverage

## Prerequisites

For local Python development:

- Python `3.13` recommended for the main app environment

For Docker deployment:

- Docker Desktop
- On the inference machine, an NVIDIA GPU is optional but recommended
- For GPU inference through Docker Desktop on Windows, WSL2 GPU support and the NVIDIA Container Toolkit path exposed through Docker Desktop must already be working

## Python Installation

### Windows

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

### macOS / Linux

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Docker Deployment Model

The root [docker-compose.yml](docker-compose.yml) describes one machine in the distributed system. Each machine uses the same Compose file and selects local services through `COMPOSE_PROFILES`.

Available profiles:

- `name-service`
- `gateway`
- `inference`
- `replica`

The `replica` profile also starts a local `qdrant` container.

### Optional GPU Override

The inference machine can enable GPU access with [docker-compose.gpu.yml](docker-compose.gpu.yml).

Use it only on the inference machine:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

Machines without a GPU should use plain `docker compose up -d --build`.

## Current Runtime Defaults

Important defaults from the code and [.env.example](.env.example):

- inference model: `Qwen/Qwen3-4B-Instruct-2507`
- embedding model: `sentence-transformers/all-MiniLM-L12-v2`
- semantic vector size: `384`
- general service timeout: `2.0s`
- gateway inference timeout: `180.0s`
- stale replica removal timeout: `3600s`

The Hugging Face and sentence-transformer caches are persisted under `.docker/`, so model downloads survive container recreation.

## Environment Variables

Every machine should start by copying the template:

```powershell
Copy-Item .env.example .env
```

Then update the machine-specific values.

Important variables:

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
- `REQUEST_TIMEOUT_SEC`
- `INFERENCE_REQUEST_TIMEOUT_SEC`
- `SEMANTIC_EMBEDDING_MODEL_ID`
- `SEMANTIC_EMBEDDING_DEVICE`
- `INFERENCE_MODEL_ID`
- `INFERENCE_BACKEND`
- `INFERENCE_DEVICE`
- `HF_TOKEN`

## Three-Machine Installation

Example layout:

- `192.168.40.211`: `name-service` + `replica-a`
- `192.168.42.80`: `inference-adapter` + `replica-b`
- `192.168.39.118`: `gateway` + `replica-c`

Start order:

1. `name-service` machine
2. `inference-adapter` machine
3. `gateway` machine

### Machine A: Name Service + Replica A

`.env`

```env
PROJECT_NAME=CacheMesh
LOG_LEVEL=INFO
ENVIRONMENT=development

COMPOSE_PROFILES=name-service,replica

GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8000
NAME_SERVICE_URL=http://192.168.40.211:8100
GATEWAY_REPLICA_TARGETS=replica-a=http://192.168.40.211:8201,replica-b=http://192.168.42.80:8202,replica-c=http://192.168.39.118:8203
GATEWAY_REPLICA_URLS=http://192.168.40.211:8201,http://192.168.42.80:8202,http://192.168.39.118:8203

NAME_SERVICE_HOST=0.0.0.0
NAME_SERVICE_PORT=8100

REPLICA_ID=replica-a
REPLICA_HOST=0.0.0.0
REPLICA_PORT=8201
REPLICA_ADVERTISED_HOST=192.168.40.211
REPLICA_ADVERTISED_PORT=8201
REPLICA_PEER_TARGETS=replica-a=http://192.168.40.211:8201,replica-b=http://192.168.42.80:8202,replica-c=http://192.168.39.118:8203
INITIAL_TOKEN_REPLICA_ID=replica-a

QDRANT_URL=http://qdrant:6333
QDRANT_HOST_PORT=6334
QDRANT_COLLECTION=cachemesh_entries
SEMANTIC_EMBEDDING_MODEL_ID=sentence-transformers/all-MiniLM-L12-v2
SEMANTIC_EMBEDDING_DEVICE=auto
SEMANTIC_VECTOR_SIZE=384
SEMANTIC_SCORE_THRESHOLD=0.72

REQUEST_TIMEOUT_SEC=2.0
INFERENCE_REQUEST_TIMEOUT_SEC=180.0
HEARTBEAT_INTERVAL_SEC=1.0
SUSPECT_AFTER_MISSES=3
UNHEALTHY_AFTER_MISSES=5

FAULT_MODE=disabled
FAULT_DURATION_SEC=10

INFERENCE_ADAPTER_URL=http://192.168.42.80:8050
ADAPTER_HOST=0.0.0.0
ADAPTER_PORT=8050
INFERENCE_BACKEND=stub
INFERENCE_MODEL_ID=Qwen/Qwen3-4B-Instruct-2507
INFERENCE_MAX_NEW_TOKENS=256
INFERENCE_TEMPERATURE=0.7
INFERENCE_TOP_P=0.9
INFERENCE_LOAD_IN_4BIT=true
INFERENCE_DEVICE=auto
```

Start:

```powershell
docker compose up -d --build
```

### Machine B: Inference Adapter + Replica B

`.env`

```env
PROJECT_NAME=CacheMesh
LOG_LEVEL=INFO
ENVIRONMENT=development

COMPOSE_PROFILES=inference,replica

GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8000
NAME_SERVICE_URL=http://192.168.40.211:8100
GATEWAY_REPLICA_TARGETS=replica-a=http://192.168.40.211:8201,replica-b=http://192.168.42.80:8202,replica-c=http://192.168.39.118:8203
GATEWAY_REPLICA_URLS=http://192.168.40.211:8201,http://192.168.42.80:8202,http://192.168.39.118:8203

NAME_SERVICE_HOST=0.0.0.0
NAME_SERVICE_PORT=8100

REPLICA_ID=replica-b
REPLICA_HOST=0.0.0.0
REPLICA_PORT=8202
REPLICA_ADVERTISED_HOST=192.168.42.80
REPLICA_ADVERTISED_PORT=8202
REPLICA_PEER_TARGETS=replica-a=http://192.168.40.211:8201,replica-b=http://192.168.42.80:8202,replica-c=http://192.168.39.118:8203
INITIAL_TOKEN_REPLICA_ID=replica-a

QDRANT_URL=http://qdrant:6333
QDRANT_HOST_PORT=6335
QDRANT_COLLECTION=cachemesh_entries
SEMANTIC_EMBEDDING_MODEL_ID=sentence-transformers/all-MiniLM-L12-v2
SEMANTIC_EMBEDDING_DEVICE=auto
SEMANTIC_VECTOR_SIZE=384
SEMANTIC_SCORE_THRESHOLD=0.72

REQUEST_TIMEOUT_SEC=2.0
INFERENCE_REQUEST_TIMEOUT_SEC=180.0
HEARTBEAT_INTERVAL_SEC=1.0
SUSPECT_AFTER_MISSES=3
UNHEALTHY_AFTER_MISSES=5

FAULT_MODE=disabled
FAULT_DURATION_SEC=10

INFERENCE_ADAPTER_URL=http://192.168.42.80:8050
ADAPTER_HOST=0.0.0.0
ADAPTER_PORT=8050
INFERENCE_BACKEND=hf_transformers
INFERENCE_MODEL_ID=Qwen/Qwen3-4B-Instruct-2507
INFERENCE_MAX_NEW_TOKENS=256
INFERENCE_TEMPERATURE=0.7
INFERENCE_TOP_P=0.9
INFERENCE_LOAD_IN_4BIT=true
INFERENCE_DEVICE=auto
HF_TOKEN=<your_hugging_face_token_here>
```

Start without GPU:

```powershell
docker compose up -d --build
```

Start with GPU:

```powershell
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

### Machine C: Gateway + Replica C

`.env`

```env
PROJECT_NAME=CacheMesh
LOG_LEVEL=INFO
ENVIRONMENT=development

COMPOSE_PROFILES=gateway,replica

GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8000
NAME_SERVICE_URL=http://192.168.40.211:8100
GATEWAY_REPLICA_TARGETS=replica-a=http://192.168.40.211:8201,replica-b=http://192.168.42.80:8202,replica-c=http://192.168.39.118:8203
GATEWAY_REPLICA_URLS=http://192.168.40.211:8201,http://192.168.42.80:8202,http://192.168.39.118:8203

NAME_SERVICE_HOST=0.0.0.0
NAME_SERVICE_PORT=8100

REPLICA_ID=replica-c
REPLICA_HOST=0.0.0.0
REPLICA_PORT=8203
REPLICA_ADVERTISED_HOST=192.168.39.118
REPLICA_ADVERTISED_PORT=8203
REPLICA_PEER_TARGETS=replica-a=http://192.168.40.211:8201,replica-b=http://192.168.42.80:8202,replica-c=http://192.168.39.118:8203
INITIAL_TOKEN_REPLICA_ID=replica-a

QDRANT_URL=http://qdrant:6333
QDRANT_HOST_PORT=6336
QDRANT_COLLECTION=cachemesh_entries
SEMANTIC_EMBEDDING_MODEL_ID=sentence-transformers/all-MiniLM-L12-v2
SEMANTIC_EMBEDDING_DEVICE=auto
SEMANTIC_VECTOR_SIZE=384
SEMANTIC_SCORE_THRESHOLD=0.72

REQUEST_TIMEOUT_SEC=2.0
INFERENCE_REQUEST_TIMEOUT_SEC=180.0
HEARTBEAT_INTERVAL_SEC=1.0
SUSPECT_AFTER_MISSES=3
UNHEALTHY_AFTER_MISSES=5

FAULT_MODE=disabled
FAULT_DURATION_SEC=10

INFERENCE_ADAPTER_URL=http://192.168.42.80:8050
ADAPTER_HOST=0.0.0.0
ADAPTER_PORT=8050
INFERENCE_BACKEND=stub
INFERENCE_MODEL_ID=Qwen/Qwen3-4B-Instruct-2507
INFERENCE_MAX_NEW_TOKENS=256
INFERENCE_TEMPERATURE=0.7
INFERENCE_TOP_P=0.9
INFERENCE_LOAD_IN_4BIT=true
INFERENCE_DEVICE=auto
```

Start:

```powershell
docker compose up -d --build
```

## Verification

Check service health:

```powershell
curl.exe http://192.168.40.211:8100/health
curl.exe http://192.168.40.211:8100/members
curl.exe http://192.168.42.80:8050/health
curl.exe http://192.168.39.118:8000/health
curl.exe http://192.168.40.211:8201/health
curl.exe http://192.168.42.80:8202/health
curl.exe http://192.168.39.118:8203/health
```

The members list should show:

- `replica-a`
- `replica-b`
- `replica-c`

Test the gateway:

```bash
curl -X POST "http://192.168.39.118:8000/cache/query" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is distributed caching?","model_id":"Qwen/Qwen3-4B-Instruct-2507","semantic_enabled":true}'
```

## UI Demo Console

To open the static UI:

```powershell
cd apps\ui
python -m http.server 3000
```

Then open:

```text
http://localhost:3000
```

Use the **Settings** tab to set:

- gateway URL
- name-service URL
- inference URL
- replica A/B/C URLs

The settings are fully editable and persist in browser storage.

## Qdrant Cleanup For Demos

To clear only the demo entries on a replica machine, delete the collection and restart the replica.

Replica A:

```bash
curl -X DELETE "http://localhost:6334/collections/cachemesh_entries" && docker compose restart replica
```

Replica B with GPU override:

```bash
curl -X DELETE "http://localhost:6335/collections/cachemesh_entries" && docker compose -f docker-compose.yml -f docker-compose.gpu.yml restart replica
```

Replica C:

```bash
curl -X DELETE "http://localhost:6336/collections/cachemesh_entries" && docker compose restart replica
```

## Tests

Run the full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Useful focused run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_config.py tests\test_gateway_service.py -q
```

## Notes

- `name-service` is in-memory and not replicated
- late replicas register again automatically and bootstrap sync from a healthy peer
- replicas keep retrying registration if they start before `name-service`
- the gateway prefers healthy replicas reported by `name-service`
- the first warm startup of the inference machine can still take a few minutes while the model loads into memory, even when files are already cached
