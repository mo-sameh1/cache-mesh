from pydantic import BaseModel

from shared.models import CacheWriteRequest


class InternalWriteLockRequest(BaseModel):
    replica_id: str
    lamport_ts: int


class InternalReplicatedWriteRequest(CacheWriteRequest):
    lamport_ts: int
    vector: list[float]
    source_replica_id: str
