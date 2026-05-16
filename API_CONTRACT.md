# CacheMesh API Contract

This file is the team agreement for parallel work. Each service may change its
internal implementation, but it should keep these request and response shapes
stable unless the team agrees to update the contract first.

The source of truth for field validation is `shared/models.py`. The FastAPI
routes use those models as `response_model`s, so each service also exposes the
same contract in its `/docs` page while it is running.

## Ownership

- Gateway owner: `services/gateway/`
- Replica and Qdrant owner: `services/replica/`
- Name service, membership, and faults owner: `services/name_service/`
- Inference owner: `services/inference_adapter/`
- Shared contract changes: `shared/models.py`, reviewed by the whole team

## Gateway

### `POST /cache/query`

Request: `CacheQueryRequest`

```json
{
  "prompt": "hello",
  "model_id": "placeholder-model",
  "semantic_enabled": true
}
```

Response: `CacheQueryResponse`

```json
{
  "service": "gateway",
  "action": "cache.query",
  "status": "placeholder",
  "detail": "Gateway query flow is scaffolded. Real replica routing is still TODO.",
  "hit": false,
  "response_text": null,
  "model_id": "placeholder-model",
  "selected_replica_id": null,
  "score": null,
  "cache_status": "not_checked"
}
```

### `POST /cache/write`

Request: `CacheWriteRequest`

```json
{
  "prompt": "hello",
  "response_text": "world",
  "model_id": "placeholder-model"
}
```

Response: `CacheWriteResponse`

```json
{
  "service": "gateway",
  "action": "cache.write",
  "status": "placeholder",
  "detail": "Gateway write flow is scaffolded. Real fan-out or coordinator logic is still TODO.",
  "stored": false,
  "replica_id": null,
  "model_id": "placeholder-model",
  "lamport_ts": null
}
```

## Name Service

### `POST /register`

Request: `RegisterNodeRequest`

```json
{
  "replica_id": "replica-a",
  "host": "replica-a",
  "port": 8201
}
```

Response: `RegisterNodeResponse`

### `POST /heartbeat`

Request: `HeartbeatRequest`

```json
{
  "replica_id": "replica-a",
  "status": "healthy"
}
```

Response: `HeartbeatResponse`

### `GET /members`

Response: `MembersResponse`

```json
{
  "service": "name-service",
  "action": "members",
  "status": "placeholder",
  "detail": "Membership listing uses the placeholder in-memory map.",
  "members": [
    {
      "replica_id": "replica-a",
      "host": "replica-a",
      "port": 8201,
      "status": "healthy"
    }
  ]
}
```

## Replica

### `POST /cache/read`

Request: `CacheReadRequest`

```json
{
  "prompt": "hello",
  "model_id": "placeholder-model",
  "semantic_enabled": true
}
```

Response: `CacheReadResponse`

### `POST /cache/write`

Request: `CacheWriteRequest`

Response: `CacheWriteResponse`

### `POST /sync/snapshot`

Request: `SnapshotRequest`

Response: `SnapshotResponse`

### `POST /sync/replay`

Request: `ReplayRequest`

Response: `ReplayResponse`

### `GET /vector-store`

Response: `VectorStoreDescriptionResponse`

## Inference Adapter

### `POST /infer`

Request: `InferRequest`

```json
{
  "prompt": "hello",
  "model_id": "placeholder-model"
}
```

Response: `InferResponse`

### `POST /infer/stream`

Request: `InferRequest`

Streaming response: `text/event-stream`

- `token` events stream generated text chunks.
- `done` events carry the final aggregated response payload as JSON.
- `error` events report runtime failures without changing the request body shape.

### Inference Runtime Settings

The inference service may use these environment variables without changing the request or response contracts:

- `INFERENCE_BACKEND`
- `INFERENCE_MODEL_ID`
- `INFERENCE_MAX_NEW_TOKENS`
- `INFERENCE_TEMPERATURE`
- `INFERENCE_TOP_P`
- `INFERENCE_LOAD_IN_4BIT`
- `INFERENCE_DEVICE`

## Fault Injection

### Gateway: `POST /admin/faults/{replica_id}`

Request: `FaultInjectionRequest`

```json
{
  "mode": "pause_node",
  "duration_sec": 10,
  "once": true
}
```

Response: `FaultInjectionResponse`

### Replica: `POST /admin/faults`

Request: `FaultInjectionRequest`

Response: `FaultInjectionResponse`

## Parallel Work Rule

If a branch needs to change one of these shapes, update `shared/models.py` and
this file first, then tell the team before implementing dependent code.
