from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Condition, RLock
from typing import Iterator

from shared.clock import LamportClock


@dataclass
class TokenState:
    last_granted: dict[str, int]
    queue: list[str] = field(default_factory=list)
    version: int = 0


class RicartAgrawalaTokenCoordinator:
    """Token-based distributed mutex with request numbers and token handoff.

    This follows the token-passing "second algorithm" family used in many
    distributed-systems course notes: a single token exists, replicas broadcast
    numbered requests when they need the critical section, and the token holder
    hands the token to the next waiting replica after it exits.

    Separate remote-writer markers are still used so reads on non-owner replicas
    wait until the distributed write is fully committed and replicated.
    """

    def __init__(
        self,
        replica_id: str,
        clock: LamportClock,
        *,
        replica_ids: list[str],
        initial_token_holder: str,
    ) -> None:
        self.replica_id = replica_id
        self.clock = clock
        self.replica_ids = sorted(set(replica_ids + [replica_id]))
        self._condition = Condition(RLock())
        self._active_readers = 0
        self._local_write_active = False
        self._remote_writers: set[str] = set()
        self._request_numbers = {replica: 0 for replica in self.replica_ids}
        self._requesting_local = False
        self._local_request_seq = 0
        self._has_token = replica_id == initial_token_holder
        self._token_version_seen = 0
        self._token: TokenState | None = None
        if self._has_token:
            self._token = TokenState(
                last_granted={replica: 0 for replica in self.replica_ids},
                version=0,
            )

    @contextmanager
    def read_guard(self) -> Iterator[None]:
        self.acquire_read()
        try:
            yield
        finally:
            self.release_read()

    @property
    def has_token(self) -> bool:
        with self._condition:
            return self._has_token

    def acquire_read(self) -> None:
        with self._condition:
            while self._local_write_active or self._remote_writers:
                self._condition.wait()
            self._active_readers += 1

    def release_read(self) -> None:
        with self._condition:
            self._active_readers -= 1
            self._condition.notify_all()

    def open_local_write_request(self) -> int:
        with self._condition:
            self._request_numbers[self.replica_id] += 1
            self._local_request_seq = self._request_numbers[self.replica_id]
            self._requesting_local = True
            self._condition.notify_all()
            return self._local_request_seq

    def should_broadcast_request(self) -> bool:
        with self._condition:
            return not self._has_token

    def note_remote_token_request(self, replica_id: str, request_seq: int) -> dict[str, int | bool]:
        with self._condition:
            self._request_numbers[replica_id] = max(self._request_numbers.get(replica_id, 0), request_seq)
            self._condition.notify_all()
            return {
                "accepted": True,
                "request_seq": self._request_numbers[replica_id],
            }

    def receive_token(
        self,
        from_replica_id: str,
        *,
        last_granted: dict[str, int],
        queue: list[str],
        version: int,
    ) -> dict[str, int | bool | str]:
        with self._condition:
            if version < self._token_version_seen:
                return {
                    "accepted": False,
                    "stale": True,
                    "holder_replica_id": self.replica_id,
                    "from_replica_id": from_replica_id,
                }
            if version == self._token_version_seen:
                if self._has_token and self._token is not None and self._token.version == version:
                    return {
                        "accepted": True,
                        "holder_replica_id": self.replica_id,
                        "from_replica_id": from_replica_id,
                    }
                return {
                    "accepted": False,
                    "stale": True,
                    "holder_replica_id": self.replica_id,
                    "from_replica_id": from_replica_id,
                }

            self._has_token = True
            self._token_version_seen = version
            normalized_last_granted = {replica: 0 for replica in self.replica_ids}
            normalized_last_granted.update(last_granted)
            self._token = TokenState(
                last_granted=normalized_last_granted,
                queue=[replica for replica in queue if replica != self.replica_id],
                version=version,
            )
            self._condition.notify_all()
            return {
                "accepted": True,
                "holder_replica_id": self.replica_id,
                "from_replica_id": from_replica_id,
            }

    def begin_local_write(self, request_seq: int) -> None:
        with self._condition:
            while (
                self._local_request_seq != request_seq
                or not self._requesting_local
                or not self._has_token
                or self._local_write_active
                or self._remote_writers
                or self._active_readers > 0
            ):
                self._condition.wait()
            self._local_write_active = True

    def finish_local_write(self, request_seq: int) -> None:
        with self._condition:
            if not self._has_token or self._token is None:
                raise RuntimeError("Cannot finish a token-based write without the token.")
            if self._local_request_seq == request_seq:
                self._token.last_granted[self.replica_id] = request_seq
            self._requesting_local = False
            self._local_request_seq = 0
            self._local_write_active = False
            self._refresh_waiting_queue_locked()
            self._condition.notify_all()

    def abort_local_write(self, request_seq: int) -> None:
        with self._condition:
            if self._local_request_seq == request_seq:
                self._requesting_local = False
                self._local_request_seq = 0
            self._local_write_active = False
            self._condition.notify_all()

    def next_token_recipient(self) -> str | None:
        with self._condition:
            if not self._has_token or self._token is None or self._local_write_active or self._requesting_local:
                return None
            self._refresh_waiting_queue_locked()
            if not self._token.queue:
                return None
            return self._token.queue[0]

    def export_token_for_transfer(self, recipient_id: str) -> dict[str, object]:
        with self._condition:
            if not self._has_token or self._token is None:
                raise RuntimeError("Cannot transfer a token that is not held locally.")
            queue = [replica for replica in self._token.queue if replica != recipient_id]
            version = self._token.version + 1
            return {
                "last_granted": dict(self._token.last_granted),
                "queue": queue,
                "version": version,
            }

    def mark_token_sent(self, recipient_id: str, version: int) -> None:
        with self._condition:
            if self._token is not None:
                self._token.queue = [replica for replica in self._token.queue if replica != recipient_id]
            self._has_token = False
            self._token = None
            self._token_version_seen = max(self._token_version_seen, version)
            self._condition.notify_all()

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

    def _refresh_waiting_queue_locked(self) -> None:
        if self._token is None:
            return
        queued = set(self._token.queue)
        eligible = []
        for replica_id in self.replica_ids:
            if replica_id == self.replica_id:
                continue
            request_number = self._request_numbers.get(replica_id, 0)
            last_granted = self._token.last_granted.get(replica_id, 0)
            if request_number == last_granted + 1 and replica_id not in queued:
                eligible.append((request_number, replica_id))

        for _, replica_id in sorted(eligible):
            self._token.queue.append(replica_id)
