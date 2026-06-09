import threading
counter = 0
def run_racy():
    global counter
    def inc():
        global counter
        for _ in range(50):
            counter += 1
    threads = [threading.Thread(target=inc) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
