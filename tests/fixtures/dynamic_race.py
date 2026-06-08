import threading

counter = 0

def increment():
    global counter
    for _ in range(100):
        counter += 1

threads = [threading.Thread(target=increment) for _ in range(5)]
for t in threads:
    t.start()
for t in threads:
    t.join()
