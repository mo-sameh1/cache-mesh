from fastapi import APIRouter, Request

from services.replica.internal_models import (
    InternalReplicatedWriteRequest,
    InternalSyncExportRequest,
    InternalTokenRequest,
    InternalTokenTransferRequest,
    InternalWriteFinishedRequest,
    InternalWriteStateRequest,
)
from shared.models import (
    CacheReadRequest,
    CacheReadResponse,
    CacheWriteRequest,
    CacheWriteResponse,
    CoordinationStatusResponse,
    FaultInjectionRequest,
    FaultInjectionResponse,
    HealthResponse,
    ReplayRequest,
    ReplayResponse,
    SnapshotRequest,
    SnapshotResponse,
    VectorStoreDescriptionResponse,
)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    return HealthResponse(**request.app.state.replica_manager.health())


@router.get("/coordination", response_model=CoordinationStatusResponse)
def coordination_status(request: Request) -> CoordinationStatusResponse:
    return CoordinationStatusResponse(**request.app.state.replica_manager.coordination_status())


@router.post("/cache/read", response_model=CacheReadResponse)
def read_cache(request: Request, payload: CacheReadRequest) -> dict:
    return request.app.state.replica_manager.read_cache(payload.model_dump())


@router.post("/cache/write", response_model=CacheWriteResponse)
def write_cache(request: Request, payload: CacheWriteRequest) -> dict:
    return request.app.state.replica_manager.write_cache(payload.model_dump())


@router.post("/sync/snapshot", response_model=SnapshotResponse)
def sync_snapshot(request: Request, payload: SnapshotRequest) -> dict:
    return request.app.state.replica_manager.snapshot(payload.model_dump())


@router.post("/sync/replay", response_model=ReplayResponse)
def sync_replay(request: Request, payload: ReplayRequest) -> dict:
    return request.app.state.replica_manager.replay(payload.model_dump())


@router.post("/admin/faults", response_model=FaultInjectionResponse)
def admin_faults(request: Request, payload: FaultInjectionRequest) -> dict:
    return request.app.state.replica_manager.arm_fault(payload.model_dump())


@router.get("/vector-store", response_model=VectorStoreDescriptionResponse)
def describe_vector_store(request: Request) -> dict:
    return request.app.state.replica_manager.describe_vector_store()


@router.post("/internal/mutex/request-token")
def request_token(request: Request, payload: InternalTokenRequest) -> dict:
    return request.app.state.replica_manager.request_internal_token(payload.model_dump())


@router.post("/internal/mutex/transfer-token")
def transfer_token(request: Request, payload: InternalTokenTransferRequest) -> dict:
    return request.app.state.replica_manager.receive_internal_token(payload.model_dump())


@router.post("/internal/locks/write-started")
def mark_write_started(request: Request, payload: InternalWriteStateRequest) -> dict:
    return request.app.state.replica_manager.mark_internal_write_started(payload.model_dump())


@router.post("/internal/locks/write-finished")
def mark_write_finished(request: Request, payload: InternalWriteFinishedRequest) -> dict:
    return request.app.state.replica_manager.mark_internal_write_finished(payload.model_dump())


@router.post("/internal/cache/replicate")
def replicate_cache(request: Request, payload: InternalReplicatedWriteRequest) -> dict:
    return request.app.state.replica_manager.apply_replicated_write(payload.model_dump())


@router.post("/internal/sync/export")
def export_sync_state(request: Request, payload: InternalSyncExportRequest) -> dict:
    return request.app.state.replica_manager.export_internal_sync_state(payload.model_dump())
