import threading
from collections import Counter, defaultdict
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
    _lock = threading.Lock()
    _access_log: dict[str, list[AccessRecord]] = defaultdict(list)
    _thread_clocks: dict[int, VectorClock] = {}
    _lock_clocks: dict[str, VectorClock] = {}
    _active = False

    @classmethod
    def start(cls):
        cls._active = True

    @classmethod
    def stop(cls):
        cls._active = False

    @classmethod
    def _get_clock(cls) -> VectorClock:
        tid = threading.get_ident()
        if tid not in cls._thread_clocks:
            with cls._lock:
                if tid not in cls._thread_clocks:
                    cls._thread_clocks[tid] = VectorClock()
        return cls._thread_clocks[tid]

    @classmethod
    def write_before(cls, var_name: str, file: str = "", line: int = 0):
        if not cls._active:
            return
        clock = cls._get_clock()
        tid = threading.get_ident()
        clock.tick(tid)
        record = AccessRecord(
            var_name=var_name,
            operation="write",
            thread_id=tid,
            clock=clock.copy(),
            location=(file, line),
        )
        with cls._lock:
            cls._access_log[var_name].append(record)

    @classmethod
    def read_before(cls, var_name: str, file: str = "", line: int = 0):
        if not cls._active:
            return
        clock = cls._get_clock()
        tid = threading.get_ident()
        clock.tick(tid)
        record = AccessRecord(
            var_name=var_name,
            operation="read",
            thread_id=tid,
            clock=clock.copy(),
            location=(file, line),
        )
        with cls._lock:
            cls._access_log[var_name].append(record)

    @classmethod
    def lock_acquire(cls, lock_name: str, file: str = "", line: int = 0):
        if not cls._active:
            return
        tid = threading.get_ident()
        clock = cls._get_clock()
        with cls._lock:
            if lock_name in cls._lock_clocks:
                clock.merge(cls._lock_clocks[lock_name])
        clock.tick(tid)

    @classmethod
    def lock_release(cls, lock_name: str, file: str = "", line: int = 0):
        if not cls._active:
            return
        clock = cls._get_clock()
        tid = threading.get_ident()
        with cls._lock:
            cls._lock_clocks[lock_name] = clock.copy()

    @classmethod
    def reset(cls):
        with cls._lock:
            cls._access_log.clear()
            cls._thread_clocks.clear()
            cls._lock_clocks.clear()
        cls._active = False

    @classmethod
    def reset_logs(cls):
        with cls._lock:
            cls._access_log.clear()
            cls._thread_clocks.clear()
            cls._lock_clocks.clear()

    @classmethod
    def _race_key(cls, r1: AccessRecord, r2: AccessRecord) -> tuple:
        tid1, tid2 = sorted([r1.thread_id, r2.thread_id])
        loc1, loc2 = sorted([r1.location, r2.location])
        return (r1.var_name, tid1, tid2, loc1, loc2)

    @classmethod
    def detect_races(cls) -> list[tuple[str, AccessRecord, AccessRecord]]:
        raw: list[tuple[str, AccessRecord, AccessRecord]] = []
        with cls._lock:
            for var_name, records in cls._access_log.items():
                for i, r1 in enumerate(records):
                    for r2 in records[i + 1 :]:
                        if r1.thread_id != r2.thread_id:
                            if r1.operation == "write" or r2.operation == "write":
                                if r1.clock.conflicts_with(r2.clock):
                                    raw.append((var_name, r1, r2))

        seen: set[tuple] = set()
        races: list[tuple[str, AccessRecord, AccessRecord]] = []
        for entry in raw:
            _, r1, r2 = entry
            key = cls._race_key(r1, r2)
            if key not in seen:
                seen.add(key)
                races.append(entry)
        return races

    @classmethod
    def format_races(cls) -> str:
        races = cls.detect_races()
        if not races:
            return "No data races detected"

        overlap = Counter()
        with cls._lock:
            for var_name, records in cls._access_log.items():
                for i, r1 in enumerate(records):
                    for r2 in records[i + 1 :]:
                        if r1.thread_id != r2.thread_id:
                            if r1.operation == "write" or r2.operation == "write":
                                if r1.clock.conflicts_with(r2.clock):
                                    key = cls._race_key(r1, r2)
                                    overlap[key] += 1

        lines = ["Data races detected:", ""]
        for var_name, r1, r2 in races:
            f1, l1 = r1.location
            f2, l2 = r2.location
            key = cls._race_key(r1, r2)
            count = overlap.get(key, 0)
            lines.append(f"  [!] `{var_name}`")
            lines.append(
                f"      Thread-{r1.thread_id} ({r1.operation})"
                f" at {f1}:{l1}"
            )
            lines.append(
                f"      Thread-{r2.thread_id} ({r2.operation})"
                f" at {f2}:{l2}"
            )
            if count > 1:
                lines.append(f"      ({count} overlapping accesses)")
            lines.append("")

        total_unique = len(races)
        total_overlap = sum(overlap.values())
        lines.append(
            f"Summary: {total_unique} unique race pair(s), "
            f"{total_overlap} total overlapping access(es)"
        )
        return "\n".join(lines)
