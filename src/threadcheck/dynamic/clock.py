from collections import defaultdict


class VectorClock:
    def __init__(self):
        self._clock: dict[int, int] = defaultdict(int)

    def tick(self, thread_id: int) -> int:
        self._clock[thread_id] += 1
        return self._clock[thread_id]

    def merge(self, other: "VectorClock"):
        for k, v in other._clock.items():
            self._clock[k] = max(self._clock.get(k, 0), v)

    def conflicts_with(self, other: "VectorClock") -> bool:
        return not (self._leq(other) or other._leq(self))

    def _leq(self, other: "VectorClock") -> bool:
        for k, v in self._clock.items():
            if v > other._clock.get(k, 0):
                return False
        return True

    def copy(self) -> "VectorClock":
        vc = VectorClock()
        vc._clock = self._clock.copy()
        return vc

    def __repr__(self) -> str:
        return f"VectorClock({dict(self._clock)})"
