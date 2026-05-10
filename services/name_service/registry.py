class MembershipRegistry:
    """In-memory placeholder for membership and heartbeat tracking."""

    def __init__(self) -> None:
        self.members: dict[str, dict] = {}

    def register(self, payload: dict) -> dict:
        replica_id = payload.get("replica_id", "unknown")
        member = {**payload, "status": payload.get("status", "healthy")}
        self.members[replica_id] = member
        return {
            "service": "name-service",
            "action": "register",
            "status": "placeholder",
            "detail": "Registration is stored in memory. Real liveness handling is still TODO.",
            "registered": True,
            "member": member,
        }

    def heartbeat(self, payload: dict) -> dict:
        replica_id = payload.get("replica_id", "unknown")
        member = self.members.setdefault(
            replica_id,
            {"replica_id": replica_id, "host": "unknown", "port": 0, "status": "unknown"},
        )
        member.update(payload)
        return {
            "service": "name-service",
            "action": "heartbeat",
            "status": "placeholder",
            "detail": "Heartbeat tracking is scaffolded. Suspect and unhealthy transitions are still TODO.",
            "accepted": True,
            "member": member,
        }

    def list_members(self) -> dict:
        return {
            "service": "name-service",
            "action": "members",
            "status": "placeholder",
            "detail": "Membership listing uses the placeholder in-memory map.",
            "members": list(self.members.values()),
        }

