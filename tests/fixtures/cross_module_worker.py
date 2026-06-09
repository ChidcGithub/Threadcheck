"""Contains a thread target function with an unprotected global write."""
counter = 0

def run():
    global counter
    for _ in range(100):
        counter += 1
