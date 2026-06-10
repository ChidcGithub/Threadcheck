import threading

counter = 0
lock = threading.Lock()


def safe_manual():
    global counter
    lock.acquire()
    counter += 1
    lock.release()


def unsafe():
    global counter
    counter += 1


threading.Thread(target=safe_manual).start()
threading.Thread(target=unsafe).start()
