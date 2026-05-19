from pydantic import BaseModel

from shared.models import CacheWriteRequest


class InternalTokenRequest(BaseModel):
    replica_id: str
    request_seq: int


class InternalTokenTransferRequest(BaseModel):
    from_replica_id: str
    last_granted: dict[str, int]
    queue: list[str]


class InternalWriteStateRequest(BaseModel):
    replica_id: str
    lamport_ts: int


class InternalWriteFinishedRequest(BaseModel):
    replica_id: str


class InternalReplicatedWriteRequest(CacheWriteRequest):
    lamport_ts: int
    vector: list[float]
    source_replica_id: str
