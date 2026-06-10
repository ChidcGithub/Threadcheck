"""Uses ThreadPoolExecutor.submit — target should be extracted."""
from concurrent.futures import ThreadPoolExecutor
import threading

counter = 0
_barrier = threading.Barrier(2)

def increment():
    _barrier.wait()
    global counter
    for _ in range(100):
        counter += 1

with ThreadPoolExecutor(max_workers=2) as ex:
    ex.submit(increment)
    ex.submit(increment)
