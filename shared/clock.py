class LamportClock:
    """Minimal Lamport clock placeholder for future distributed ordering."""

    def __init__(self, initial_value: int = 0) -> None:
        self.value = initial_value

    def tick(self) -> int:
        self.value += 1
        return self.value

    def update(self, remote_value: int) -> int:
        self.value = max(self.value, remote_value) + 1
        return self.value

