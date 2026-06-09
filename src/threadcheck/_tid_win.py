import threading


def current_tid() -> int:
    return threading.get_ident()
