"""Script with intentional data races — used by threadcheck demo."""
import threading

counter = 0
results = []
lock = threading.Lock()


def increment():
    global counter
    for _ in range(100):
        counter += 1
        results.append(counter)


def safe_increment():
    global counter
    for _ in range(100):
        with lock:
            counter += 1


threads = [threading.Thread(target=increment) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print(f"Final counter (racy): {counter}")
