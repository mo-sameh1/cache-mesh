from fastapi import APIRouter
from pydantic import BaseModel
from services.name_service.registry import MembershipRegistry

router=APIRouter()
registry=MembershipRegistry()

class RegisterRequest(BaseModel):
    replica_id:str
    host:str
    port:int

class HeartbeatRequest(BaseModel):
    replica_id:str

@router.post("/register")
def register(data:RegisterRequest):
    return registry.register(data.model_dump())

@router.post("/heartbeat")
def heartbeat(data:HeartbeatRequest):
    return registry.heartbeat(data.model_dump())

@router.get("/members")
def members():
    return {"members": registry.members_list()}

@router.get("/healthy-members")
def healthy():
    return {"members": registry.healthy_members()}
