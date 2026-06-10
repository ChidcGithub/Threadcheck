import threading

shared_dict = {"key": 0}
lock = threading.Lock()


def thread_writer():
    global shared_dict
    for _ in range(100):
        with lock:
            shared_dict["key"] += 1


def thread_unsafe_writer():
    global shared_dict
    for _ in range(100):
        shared_dict["key"] += 1


threads = []
for _ in range(2):
    t = threading.Thread(target=thread_unsafe_writer)
    threads.append(t)
    t.start()
for t in threads:
    t.join()
