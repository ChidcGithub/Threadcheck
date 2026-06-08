import threading

lock = threading.Lock()
shared = []

def worker():
    for i in range(100):
        with lock:
            shared.append(i)

threads = [threading.Thread(target=worker) for _ in range(5)]
for t in threads:
    t.start()
for t in threads:
    t.join()
