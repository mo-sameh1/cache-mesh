from shared.faults import FaultController


class ReplicaFaultService:
    """Placeholder for fault injection behavior on a replica."""

    def __init__(self, controller: FaultController | None = None) -> None:
        self.controller = controller or FaultController()

    def arm_fault(self, payload: dict) -> dict:
        self.controller.arm(payload)
        return {
            "service": "replica",
            "action": "admin.faults",
            "status": "placeholder",
            "detail": "Fault injection is scaffolded. Real pause or timeout behavior is still TODO.",
            "accepted": True,
            "target_replica_id": None,
            "active_fault": payload,
        }