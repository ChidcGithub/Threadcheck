"""Uses ThreadPoolExecutor.submit — target should be extracted."""
from concurrent.futures import ThreadPoolExecutor

counter = 0

def increment():
    global counter
    counter += 1

with ThreadPoolExecutor(max_workers=2) as ex:
    ex.submit(increment)
    ex.submit(increment)
