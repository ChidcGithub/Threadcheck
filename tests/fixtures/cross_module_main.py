"""Launches a thread targeting a function defined in cross_module_worker.py."""
import threading
from .cross_module_worker import run

t = threading.Thread(target=run)
t.start()
t.join()
