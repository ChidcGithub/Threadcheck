"""Thread 1 reads, thread 2 writes — should be detected as read-write race."""
import threading

counter = 0

def writer():
    global counter
    for _ in range(50):
        counter += 1

def reader():
    global counter
    for _ in range(50):
        _ = counter

t1 = threading.Thread(target=writer)
t2 = threading.Thread(target=reader)
t1.start()
t2.start()
t1.join()
t2.join()
