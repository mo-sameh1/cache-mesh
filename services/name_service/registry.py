"""Membership registry with real liveness state transitions.

State machine per replica:
  registered  ──heartbeat──►  healthy
  healthy     ──suspect_after_misses * heartbeat_interval seconds──►  suspect
  suspect     ──unhealthy_after_misses * heartbeat_interval seconds──►  unhealthy
  any state   ──new heartbeat──►  healthy
"""
from __future__ import annotations

import time
from typing import Dict, Optional

from shared.config import NameServiceSettings


def _compute_status(last_heartbeat: float, now: float, suspect_after: float, unhealthy_after: float) -> str:
    """Derive liveness status from elapsed time since last heartbeat."""
    elapsed = now - last_heartbeat
    if elapsed < suspect_after:
        return "healthy"
    if elapsed < unhealthy_after:
        return "suspect"
    return "unhealthy"


class MembershipRegistry:
    """In-memory membership registry with healthy / suspect / unhealthy transitions."""

    def __init__(self, settings: NameServiceSettings | None = None) -> None:
        settings = settings or NameServiceSettings()
        self.heartbeat_interval = settings.heartbeat_interval_sec
        self.suspect_after = self.heartbeat_interval * settings.suspect_after_misses
        self.unhealthy_after = self.heartbeat_interval * settings.unhealthy_after_misses
        self.removal_after = settings.member_removal_timeout_sec
        # replica_id → {replica_id, host, port, last_heartbeat}
        self._members: Dict[str, dict] = {}

    @property
    def members(self) -> Dict[str, dict]:
        return self._members

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
            "status": _compute_status(raw["last_heartbeat"], t, self.suspect_after, self.unhealthy_after),
        }

    def _prune_expired_members(self, now: float, *, exclude_replica_id: str | None = None) -> None:
        expired_members = [
            replica_id
            for replica_id, raw in self._members.items()
            if replica_id != exclude_replica_id and now - raw["last_heartbeat"] >= self.removal_after
        ]
        for replica_id in expired_members:
            self._members.pop(replica_id, None)

    # ------------------------------------------------------------------
    # public API

    def register(self, payload: dict) -> dict:
        replica_id = payload["replica_id"]
        now = time.monotonic()
        self._prune_expired_members(now, exclude_replica_id=replica_id)
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
        self._prune_expired_members(now, exclude_replica_id=replica_id)
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
        self._prune_expired_members(now)
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

