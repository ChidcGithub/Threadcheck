import threading

shared_data = []

def worker():
    for i in range(100):
        shared_data.append(i)

threads = [threading.Thread(target=worker) for _ in range(5)]
for t in threads:
    t.start()
for t in threads:
    t.join()
