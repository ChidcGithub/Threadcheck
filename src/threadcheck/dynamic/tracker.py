import threading
from collections import defaultdict
from dataclasses import dataclass, field

from .clock import VectorClock


@dataclass
class AccessRecord:
    var_name: str
    operation: str
    thread_id: int
    clock: VectorClock = field(default_factory=VectorClock)
    location: tuple = ("", 0)


class ThreadCheckTracker:
    _tls = threading.local()
    _lock = threading.Lock()
    _access_log: dict[str, list[AccessRecord]] = defaultdict(list)
    _thread_clocks: dict[int, VectorClock] = {}
    _active = False

    @classmethod
    def start(cls):
        cls._active = True

    @classmethod
    def stop(cls):
        cls._active = False

    @classmethod
    def _ensure_clock(cls):
        if not hasattr(cls._tls, "clock"):
            cls._tls.clock = VectorClock()
            tid = threading.get_ident()
            with cls._lock:
                cls._thread_clocks[tid] = cls._tls.clock

    @classmethod
    def write_before(cls, var_name: str, file: str = "", line: int = 0):
        if not cls._active:
            return
        cls._ensure_clock()
        tid = threading.get_ident()
        cls._tls.clock.tick(tid)
        record = AccessRecord(
            var_name=var_name,
            operation="write",
            thread_id=tid,
            clock=cls._tls.clock.copy(),
            location=(file, line),
        )
        with cls._lock:
            cls._access_log[var_name].append(record)

    @classmethod
    def read_before(cls, var_name: str, file: str = "", line: int = 0):
        if not cls._active:
            return
        cls._ensure_clock()
        tid = threading.get_ident()
        cls._tls.clock.tick(tid)
        record = AccessRecord(
            var_name=var_name,
            operation="read",
            thread_id=tid,
            clock=cls._tls.clock.copy(),
            location=(file, line),
        )
        with cls._lock:
            cls._access_log[var_name].append(record)

    @classmethod
    def lock_acquire(cls, lock_name: str, file: str = "", line: int = 0):
        if not cls._active:
            return
        cls._ensure_clock()
        tid = threading.get_ident()
        with cls._lock:
            if lock_name in cls._thread_clocks:
                cls._tls.clock.merge(cls._thread_clocks[lock_name])
        cls._tls.clock.tick(tid)

    @classmethod
    def lock_release(cls, lock_name: str, file: str = "", line: int = 0):
        if not cls._active:
            return
        cls._ensure_clock()
        tid = threading.get_ident()
        with cls._lock:
            cls._thread_clocks[lock_name] = cls._tls.clock.copy()

    @classmethod
    def reset(cls):
        with cls._lock:
            cls._access_log.clear()
            cls._thread_clocks.clear()
        cls._active = False

    @classmethod
    def detect_races(cls) -> list[tuple[str, AccessRecord, AccessRecord]]:
        races: list[tuple[str, AccessRecord, AccessRecord]] = []
        with cls._lock:
            for var_name, records in cls._access_log.items():
                for i, r1 in enumerate(records):
                    for r2 in records[i + 1 :]:
                        if r1.thread_id != r2.thread_id:
                            if r1.operation == "write" or r2.operation == "write":
                                if r1.clock.conflicts_with(r2.clock):
                                    races.append((var_name, r1, r2))
        return races

    @classmethod
    def format_races(cls) -> str:
        races = cls.detect_races()
        if not races:
            return "No data races detected"

        lines = ["Data races detected:", ""]
        for var_name, r1, r2 in races:
            f1, l1 = r1.location
            f2, l2 = r2.location
            lines.append(f"  [!] `{var_name}`")
            lines.append(
                f"      Thread-{r1.thread_id} ({r1.operation})"
                f" at {f1}:{l1}"
            )
            lines.append(
                f"      Thread-{r2.thread_id} ({r2.operation})"
                f" at {f2}:{l2}"
            )
            lines.append("")
        return "\n".join(lines)
