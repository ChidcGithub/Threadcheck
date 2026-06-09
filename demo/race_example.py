"""Script with intentional data races — used by threadcheck demo."""
import threading

counter = 0
results = []


def increment():
    global counter
    for _ in range(50):
        counter += 1
        results.append(counter)


threads = [threading.Thread(target=increment) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print(f"Final counter (unexpected due to race): {counter}")
