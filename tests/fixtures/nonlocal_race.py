import threading

def make_counter():
    count = 0
    lock = threading.Lock()

    def increment():
        nonlocal count
        for _ in range(1000):
            with lock:
                count += 1

    def increment_unsafe():
        nonlocal count
        for _ in range(1000):
            count += 1

    t1 = threading.Thread(target=increment_unsafe)
    t2 = threading.Thread(target=increment)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    return count
