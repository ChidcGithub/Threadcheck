"""Script with intentional data races — used by threadcheck demo."""
import threading
from concurrent.futures import ThreadPoolExecutor

counter = 0
results = []
shared_dict = {}
lock = threading.Lock()


def increment():
    global counter
    for _ in range(100):
        counter += 1
        results.append(counter)


def safe_increment():
    global counter
    for _ in range(100):
        with lock:
            counter += 1


def dict_worker():
    for i in range(50):
        shared_dict[i] = i * 2


def list_worker():
    for i in range(50):
        results.append(i)


class MyThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.value = 0

    def run(self):
        for _ in range(50):
            self.value += 1


threads = [threading.Thread(target=increment) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()

safe_threads = [threading.Thread(target=safe_increment) for _ in range(4)]
for t in safe_threads:
    t.start()
for t in safe_threads:
    t.join()

dict_threads = [threading.Thread(target=dict_worker) for _ in range(2)]
for t in dict_threads:
    t.start()
for t in dict_threads:
    t.join()

with ThreadPoolExecutor(max_workers=2) as ex:
    for _ in range(4):
        ex.submit(list_worker)

mt = MyThread()
mt.start()
mt.join()

print(f"Final counter (racy): {counter}")
