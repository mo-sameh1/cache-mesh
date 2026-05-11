from fastapi import APIRouter

from shared.models import (
    HealthResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    MembersResponse,
    RegisterNodeRequest,
    RegisterNodeResponse,
)
from services.name_service.registry import MembershipRegistry


router = APIRouter()
registry = MembershipRegistry()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="name-service", status="ok", detail="Name service placeholder is running.")


@router.post("/register", response_model=RegisterNodeResponse)
def register(request: RegisterNodeRequest) -> dict:
    return registry.register(request.model_dump())


@router.post("/heartbeat", response_model=HeartbeatResponse)
def heartbeat(request: HeartbeatRequest) -> dict:
    return registry.heartbeat(request.model_dump())


@router.get("/members", response_model=MembersResponse)
def members() -> dict:
    return registry.list_members()

