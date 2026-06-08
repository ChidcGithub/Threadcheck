import threading

class MyThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.value = 0

    def run(self):
        for _ in range(1000):
            self.value += 1

threads = [MyThread() for _ in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()
