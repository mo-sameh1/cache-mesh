class FaultController:
    """In-memory placeholder for fault injection state."""

    def __init__(self) -> None:
        self.active_fault: dict | None = None

    def arm(self, payload: dict) -> None:
        self.active_fault = payload

    def current(self) -> dict | None:
        return self.active_fault

