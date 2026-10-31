"""Best-effort Windows idle-sleep prevention for one synchronous wait."""

import ctypes
import sys
from contextlib import contextmanager

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def _execution_state():
    from ctypes import wintypes

    function = ctypes.WinDLL("kernel32").SetThreadExecutionState
    function.argtypes = (wintypes.DWORD,)
    function.restype = wintypes.DWORD
    return function


def _warn(reason):
    if sys.stderr is not None:
        try:
            print(f"warning: --keep-awake {reason}; the system may sleep.", file=sys.stderr)
        except (OSError, ValueError):
            # An unavailable diagnostic stream must not replace the wait's result or exception.
            pass


@contextmanager
def keep_awake():
    """Request system availability on this thread, then restore its previous state."""
    if sys.platform != "win32":
        _warn("is available only on Windows")
        yield
        return
    try:
        set_state = _execution_state()
        previous = set_state(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    except (AttributeError, OSError) as exc:
        _warn(f"could not request system availability ({exc})")
        yield
        return
    if not previous:
        _warn("could not request system availability")
        yield
        return
    try:
        yield
    finally:
        try:
            restored = set_state(previous | ES_CONTINUOUS)
        except (AttributeError, OSError) as exc:
            _warn(f"could not restore the previous thread state ({exc})")
        else:
            if not restored:
                _warn("could not restore the previous thread state")
