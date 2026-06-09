import threading


def current_tid() -> int:
    ct = threading.current_thread()
    native = ct.native_id
    if native is not None:
        return native
    return id(ct)
