import threading

counter = 0
lock = threading.Lock()


def thread_unsafe():
    global counter
    counter += 1  # threadcheck: ignore


def thread_safe():
    global counter
    with lock:
        counter += 1


def thread_also_unsafe():
    global counter
    counter -= 1


# threadcheck: ignore-start
def thread_region_unsafe():
    global counter
    counter += 2
# threadcheck: ignore-end


def thread_post_region():
    global counter
    counter += 3
