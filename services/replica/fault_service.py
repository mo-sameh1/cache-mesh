from __future__ import annotations

import time

from fastapi import HTTPException

from shared.faults import FaultController


class ReplicaFaultService:
    """Fault injection controller for a single replica."""

    def __init__(self, controller: FaultController | None = None) -> None:
        self.controller = controller or FaultController()

    def arm_fault(self, payload: dict) -> dict:
        self.controller.arm(payload)
        current = self.controller.current()
        return {
            "service": "replica",
            "action": "admin.faults",
            "status": "ok",
            "detail": (
                f"Fault mode {payload.get('mode', 'disabled')!r} armed for "
                f"{payload.get('duration_sec', 10)}s "
                f"(once={payload.get('once', True)})."
            ),
            "accepted": True,
            "target_replica_id": None,
            "active_fault": current,
        }

    def check_and_apply(self) -> None:
        fault = self.controller.trigger()
        if fault is None:
            return

        mode = fault["mode"]
        duration = fault.get("duration_sec", 0)

        if mode == "pause_node":
            time.sleep(duration)
        elif mode == "error_response":
            raise HTTPException(
                status_code=503,
                detail="Fault injection: error_response active on this replica.",
            )
        elif mode == "slow_response":
            time.sleep(min(duration, 2))
 