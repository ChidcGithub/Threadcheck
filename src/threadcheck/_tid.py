"""Platform thread ID — replaced by CI with platform-specific variant."""
import sys
import threading


def current_tid() -> int:
    if sys.platform == "win32":
        return threading.get_ident()
    ct = threading.current_thread()
    native = ct.native_id
    if native is not None:
        return native
    return id(ct)
