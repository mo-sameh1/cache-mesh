from shared.faults import FaultController
from shared.protocol import placeholder_response


class ReplicaFaultService:
    """Placeholder for fault injection behavior on a replica."""

    def __init__(self) -> None:
        self.controller = FaultController()

    def arm_fault(self, payload: dict) -> dict:
        self.controller.arm(payload)
        return placeholder_response(
            service="replica",
            action="admin.faults",
            detail="Fault injection is scaffolded only. Real pause / timeout behavior is still TODO.",
            received=payload,
        )

