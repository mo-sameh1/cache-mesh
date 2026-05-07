from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    service: str
    status: str
    detail: str


class CacheQueryRequest(BaseModel):
    prompt: str = Field(..., description="Prompt to query through the gateway.")
    model_id: str = Field(default="placeholder-model")


class CacheWriteRequest(BaseModel):
    prompt: str
    response_text: str
    model_id: str = "placeholder-model"


class CacheReadRequest(BaseModel):
    prompt: str
    model_id: str = "placeholder-model"
    semantic_enabled: bool = True


class FaultInjectionRequest(BaseModel):
    mode: str = "disabled"
    duration_sec: int = 10
    once: bool = True


class RegisterNodeRequest(BaseModel):
    replica_id: str
    host: str
    port: int


class HeartbeatRequest(BaseModel):
    replica_id: str
    status: str = "healthy"


class SnapshotRequest(BaseModel):
    replica_id: str
    since_lamport_ts: int | None = None


class ReplayRequest(BaseModel):
    replica_id: str
    operation_count: int = 0


class InferRequest(BaseModel):
    prompt: str
    model_id: str = "placeholder-model"

