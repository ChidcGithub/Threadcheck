import threading

class Counter:
    def __init__(self):
        self.count = 0
        self.lock = threading.Lock()

    def increment(self):
        for _ in range(1000):
            with self.lock:
                self.count += 1

counter = Counter()
threads = [threading.Thread(target=counter.increment) for _ in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()
