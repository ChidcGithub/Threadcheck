"""Script with __name__ guard — should execute when run via threadcheck run."""
import threading

counter = 0

def increment():
    global counter
    for _ in range(100):
        counter += 1

if __name__ == "__main__":
    threads = [threading.Thread(target=increment) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"Result: {counter}")
