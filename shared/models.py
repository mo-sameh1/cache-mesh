from typing import List, Optional

from pydantic import BaseModel, Field


class ContractResponse(BaseModel):
    service: str
    action: str
    status: str = "placeholder"
    detail: str


class HealthResponse(BaseModel):
    service: str
    status: str
    detail: str


class CacheQueryRequest(BaseModel):
    prompt: str = Field(..., description="Prompt to query through the gateway.")
    model_id: str = Field(default="placeholder-model")
    semantic_enabled: bool = True


class CacheQueryResponse(ContractResponse):
    hit: bool
    response_text: Optional[str] = None
    model_id: str = "placeholder-model"
    selected_replica_id: Optional[str] = None
    score: Optional[float] = None
    cache_status: str = "unknown"


class CacheWriteRequest(BaseModel):
    prompt: str
    response_text: str
    model_id: str = "placeholder-model"


class CacheWriteResponse(ContractResponse):
    stored: bool
    replica_id: Optional[str] = None
    model_id: str = "placeholder-model"
    lamport_ts: Optional[int] = None


class CacheReadRequest(BaseModel):
    prompt: str
    model_id: str = "placeholder-model"
    semantic_enabled: bool = True


class CacheReadResponse(ContractResponse):
    hit: bool
    response_text: Optional[str] = None
    replica_id: Optional[str] = None
    model_id: str = "placeholder-model"
    score: Optional[float] = None


class CoordinationStatusResponse(ContractResponse):
    replica_id: str
    has_token: bool
    local_write_active: bool
    remote_writers: List[str] = Field(default_factory=list)
    active_reader_count: int = 0
    requesting_local: bool = False
    local_request_seq: int = 0
    token_queue: List[str] = Field(default_factory=list)
    token_version: Optional[int] = None
    pending_token_transfer_to: Optional[str] = None


class FaultInjectionRequest(BaseModel):
    mode: str = "disabled"
    duration_sec: int = 10
    once: bool = True


class FaultState(BaseModel):
    mode: str
    duration_sec: int
    once: bool


class FaultInjectionResponse(ContractResponse):
    accepted: bool
    target_replica_id: Optional[str] = None
    active_fault: Optional[FaultState] = None


class RegisterNodeRequest(BaseModel):
    replica_id: str
    host: str
    port: int


class ReplicaMember(BaseModel):
    replica_id: str
    host: str
    port: int
    status: str = "healthy"


class RegisterNodeResponse(ContractResponse):
    registered: bool
    member: ReplicaMember


class HeartbeatRequest(BaseModel):
    replica_id: str
    status: str = "healthy"


class HeartbeatResponse(ContractResponse):
    accepted: bool
    member: ReplicaMember


class MembersResponse(ContractResponse):
    members: List[ReplicaMember] = Field(default_factory=list)


class SnapshotRequest(BaseModel):
    replica_id: str
    since_lamport_ts: Optional[int] = None


class SnapshotResponse(ContractResponse):
    accepted: bool
    replica_id: str
    since_lamport_ts: Optional[int] = None
    snapshot_id: Optional[str] = None

class ReplayRequest(BaseModel):
    replica_id: str
    operation_count: int = 0
    snapshot_id: Optional[str] = None


class ReplayResponse(ContractResponse):
    accepted: bool
    replica_id: str
    replayed_operations: int = 0


class InferRequest(BaseModel):
    prompt: str
    model_id: str = "placeholder-model"


class InferResponse(ContractResponse):
    response_text: str
    model_id: str = "placeholder-model"
    provider: str = "placeholder"


class VectorStoreDescriptionResponse(ContractResponse):
    qdrant_url: Optional[str] = None
    collection: str

