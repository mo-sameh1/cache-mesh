from fastapi import APIRouter

from shared.models import HealthResponse, HeartbeatRequest, RegisterNodeRequest
from services.name_service.registry import MembershipRegistry


router = APIRouter()
registry = MembershipRegistry()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="name-service", status="ok", detail="Name service placeholder is running.")


@router.post("/register")
def register(request: RegisterNodeRequest) -> dict:
    return registry.register(request.model_dump())


@router.post("/heartbeat")
def heartbeat(request: HeartbeatRequest) -> dict:
    return registry.heartbeat(request.model_dump())


@router.get("/members")
def members() -> dict:
    return registry.list_members()

