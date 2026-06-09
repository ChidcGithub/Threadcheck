"""Both static and dynamic: nested with lock1, lock2: should suppress race."""
import threading

counter = 0
lock_a = threading.Lock()
lock_b = threading.Lock()

def increment():
    global counter
    for _ in range(100):
        with lock_a, lock_b:
            counter += 1

threads = [threading.Thread(target=increment) for _ in range(2)]
for t in threads:
    t.start()
for t in threads:
    t.join()
