import threading


def make_counter():
    lock = threading.Lock()
    counter = 0

    def inner():
        nonlocal counter
        with lock:
            for _ in range(100):
                counter += 1
    return inner


f = make_counter()
threads = [threading.Thread(target=f) for _ in range(2)]
for t in threads:
    t.start()
for t in threads:
    t.join()
