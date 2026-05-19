"""Membership registry with real liveness state transitions.

State machine per replica:
  registered  ──heartbeat──►  healthy
  healthy     ──SUSPECT_THRESHOLD elapsed──►  suspect
  suspect     ──UNHEALTHY_THRESHOLD elapsed──►  unhealthy
  any state   ──new heartbeat──►  healthy
"""
from __future__ import annotations

import time
from typing import Dict, Optional

# How often replicas are expected to send heartbeats (seconds).
HEARTBEAT_INTERVAL: float = 10.0
# Transition thresholds relative to last heartbeat.
SUSPECT_AFTER: float = 1.5 * HEARTBEAT_INTERVAL   # 15 s
UNHEALTHY_AFTER: float = 3.0 * HEARTBEAT_INTERVAL  # 30 s


def _compute_status(last_heartbeat: float, now: float) -> str:
    """Derive liveness status from elapsed time since last heartbeat."""
    elapsed = now - last_heartbeat
    if elapsed < SUSPECT_AFTER:
        return "healthy"
    if elapsed < UNHEALTHY_AFTER:
        return "suspect"
    return "unhealthy"


class MembershipRegistry:
    """In-memory membership registry with healthy / suspect / unhealthy transitions."""

    def __init__(self) -> None:
        # replica_id → {replica_id, host, port, last_heartbeat}
        self._members: Dict[str, dict] = {}

    # ------------------------------------------------------------------
    # internal helpers

    def _public_view(self, replica_id: str, now: Optional[float] = None) -> dict:
        """Return the contract-shaped member dict with a computed live status."""
        raw = self._members[replica_id]
        t = now if now is not None else time.monotonic()
        return {
            "replica_id": raw["replica_id"],
            "host": raw["host"],
            "port": raw["port"],
            "status": _compute_status(raw["last_heartbeat"], t),
        }

    # ------------------------------------------------------------------
    # public API

    def register(self, payload: dict) -> dict:
        replica_id = payload["replica_id"]
        now = time.monotonic()
        self._members[replica_id] = {
            "replica_id": replica_id,
            "host": payload.get("host", "unknown"),
            "port": payload.get("port", 0),
            "last_heartbeat": now,
        }
        member = self._public_view(replica_id, now)
        return {
            "service": "name-service",
            "action": "register",
            "status": "ok",
            "detail": f"Replica {replica_id!r} registered and marked healthy.",
            "registered": True,
            "member": member,
        }

    def heartbeat(self, payload: dict) -> dict:
        replica_id = payload["replica_id"]
        now = time.monotonic()
        if replica_id not in self._members:
            # Auto-register unknown replicas that heartbeat before /register.
            self._members[replica_id] = {
                "replica_id": replica_id,
                "host": "unknown",
                "port": 0,
                "last_heartbeat": now,
            }
        else:
            self._members[replica_id]["last_heartbeat"] = now
        member = self._public_view(replica_id, now)
        return {
            "service": "name-service",
            "action": "heartbeat",
            "status": "ok",
            "detail": f"Heartbeat from {replica_id!r} recorded; status is {member['status']!r}.",
            "accepted": True,
            "member": member,
        }

    def list_members(self, *, healthy_only: bool = False) -> dict:
        now = time.monotonic()
        members = [self._public_view(rid, now) for rid in self._members]
        if healthy_only:
            members = [m for m in members if m["status"] == "healthy"]
        return {
            "service": "name-service",
            "action": "members",
            "status": "ok",
            "detail": f"{len(members)} member(s) returned.",
            "members": members,
        }

