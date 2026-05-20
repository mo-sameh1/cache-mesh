"""Fault injection state manager.

Keeps the existing FaultController class so all current callers compile
without changes.  Adds proper mode validation, duration-based auto-expiry,
once-trigger semantics, and an explicit disarm.
"""
from __future__ import annotations

import time
from typing import Optional

VALID_MODES: frozenset[str] = frozenset(
    {"disabled", "pause_node", "error_response", "slow_response"}
)


class FaultController:
    """In-memory fault injection state for a single replica."""

    def __init__(self) -> None:
        self._active_fault: dict | None = None
        self._armed_at: float | None = None

    # ------------------------------------------------------------------
    # public API (backward-compatible)

    def arm(self, payload: dict) -> None:
        """Arm a fault.

        Expected keys: mode (str), duration_sec (int), once (bool).
        Raises ValueError for unknown modes.
        """
        mode = payload.get("mode", "disabled")
        if mode not in VALID_MODES:
            raise ValueError(
                f"Unknown fault mode {mode!r}. Valid modes: {sorted(VALID_MODES)}"
            )
        self._active_fault = {
            "mode": mode,
            "duration_sec": int(payload.get("duration_sec", 10)),
            "once": bool(payload.get("once", True)),
            "triggered": False,
        }
        self._armed_at = time.monotonic()

    def current(self) -> dict | None:
        """Return the active fault dict, or None if no fault is armed / expired."""
        if self._active_fault is None:
            return None
        elapsed = time.monotonic() - (self._armed_at or 0.0)
        if elapsed >= self._active_fault["duration_sec"]:
            # fault window has closed — auto-disarm
            self._active_fault = None
            self._armed_at = None
            return None
        return self._active_fault

    # ------------------------------------------------------------------
    # extended API

    def is_active(self) -> bool:
        """True while a non-expired fault is armed."""
        return self.current() is not None

    def trigger(self) -> Optional[dict]:
        """Signal that the fault is being applied to an incoming request.

        Returns a copy of the fault dict if it should fire, else None.
        For once=True faults, disarms the fault on the first trigger so
        only a single request is affected.
        """
        fault = self.current()
        if fault is None:
            return None
        fired = dict(fault)
        if fault["once"] and not fault["triggered"]:
            fault["triggered"] = True
            # disarm immediately so subsequent requests are not affected
            self._active_fault = None
            self._armed_at = None
        return fired

    def disarm(self) -> None:
        """Explicitly clear any armed fault."""
        self._active_fault = None
        self._armed_at = None

