from contextlib import contextmanager
from dataclasses import dataclass
from threading import Condition, RLock
from typing import Iterator

from shared.clock import LamportClock


@dataclass(frozen=True, order=True)
class WriteRequest:
    lamport_ts: int
    replica_id: str


class DistributedReadWriteCoordinator:
    """Coordinates local reads with Lamport-ordered distributed writes."""

    def __init__(self, replica_id: str, clock: LamportClock) -> None:
        self.replica_id = replica_id
        self.clock = clock
        self._condition = Condition(RLock())
        self._active_readers = 0
        self._local_request: WriteRequest | None = None
        self._local_write_active = False
        self._remote_writers: set[str] = set()

    @contextmanager
    def read_guard(self) -> Iterator[None]:
        self.acquire_read()
        try:
            yield
        finally:
            self.release_read()

    def acquire_read(self) -> None:
        with self._condition:
            while self._local_request is not None or self._local_write_active or self._remote_writers:
                self._condition.wait()
            self._active_readers += 1

    def release_read(self) -> None:
        with self._condition:
            self._active_readers -= 1
            self._condition.notify_all()

    def open_local_write_request(self) -> WriteRequest:
        with self._condition:
            request = WriteRequest(self.clock.tick(), self.replica_id)
            self._local_request = request
            self._condition.notify_all()
            return request

    def begin_local_write(self, request: WriteRequest) -> int:
        with self._condition:
            while self._active_readers > 0 or self._remote_writers or self._local_write_active:
                self._condition.wait()
            if self._local_request != request:
                raise RuntimeError("Write request is no longer active.")
            self._local_write_active = True
            return request.lamport_ts

    def finish_local_write(self, request: WriteRequest) -> None:
        with self._condition:
            if self._local_request == request:
                self._local_request = None
            self._local_write_active = False
            self._condition.notify_all()

    def abort_local_write(self, request: WriteRequest) -> None:
        with self._condition:
            if self._local_request == request:
                self._local_request = None
            self._condition.notify_all()

    def grant_remote_write_request(self, replica_id: str, lamport_ts: int) -> dict[str, int | bool]:
        remote_request = WriteRequest(lamport_ts, replica_id)
        with self._condition:
            self.clock.update(lamport_ts)
            while self._should_defer(remote_request):
                self._condition.wait()
            return {
                "accepted": True,
                "lamport_ts": self.clock.tick(),
            }

    def mark_remote_write_started(self, replica_id: str, lamport_ts: int) -> dict[str, int | bool]:
        with self._condition:
            self.clock.update(lamport_ts)
            while self._active_readers > 0 or self._local_write_active:
                self._condition.wait()
            self._remote_writers.add(replica_id)
            self._condition.notify_all()
            return {
                "accepted": True,
                "lamport_ts": self.clock.tick(),
            }

    def mark_remote_write_finished(self, replica_id: str) -> dict[str, bool]:
        with self._condition:
            self._remote_writers.discard(replica_id)
            self._condition.notify_all()
            return {"accepted": True}

    def _should_defer(self, remote_request: WriteRequest) -> bool:
        if self._remote_writers:
            return True
        if self._local_request is None:
            return False
        return self._local_request < remote_request
