from shared.protocol import placeholder_response


class MembershipRegistry:
    """In-memory placeholder for membership and heartbeat tracking."""

    def __init__(self) -> None:
        self.members: dict[str, dict] = {}

    def register(self, payload: dict) -> dict:
        replica_id = payload.get("replica_id", "unknown")
        self.members[replica_id] = payload
        return placeholder_response(
            service="name-service",
            action="register",
            detail="Registration is stored in a placeholder in-memory map. Real liveness handling is still TODO.",
            member=payload,
        )

    def heartbeat(self, payload: dict) -> dict:
        replica_id = payload.get("replica_id", "unknown")
        self.members.setdefault(replica_id, {}).update(payload)
        return placeholder_response(
            service="name-service",
            action="heartbeat",
            detail="Heartbeat tracking is scaffolded only. Suspect / unhealthy transitions are still TODO.",
            member=payload,
        )

    def list_members(self) -> dict:
        return placeholder_response(
            service="name-service",
            action="members",
            detail="Membership listing is scaffolded only. Returned values are from the placeholder in-memory map.",
            members=self.members,
        )

