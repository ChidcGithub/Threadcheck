import threading

def worker():
    local = []
    for i in range(100):
        local.append(i)
    return local

threads = [threading.Thread(target=worker) for _ in range(5)]
for t in threads:
    t.start()
for t in threads:
    t.join()
