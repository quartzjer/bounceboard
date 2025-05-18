import logging
import platform

from .backends import get_backend, PyperclipBackend

_backend = get_backend(platform.system())
_fallback = PyperclipBackend()

def get_content():
    try:
        result = _backend.get_content()
        if result is not None:
            return result
    except Exception:
        logging.exception(
            f"Native clipboard access failed for {platform.system()}, defaulting to text-only"
        )
    return _fallback.get_content()

def set_content(clipboard, temp_dir=None):
    try:
        if _backend.set_content(clipboard, temp_dir):
            return True
    except Exception:
        logging.exception(
            f"Native clipboard access failed for {platform.system()}, defaulting to text-only"
        )
    return _fallback.set_content(clipboard, temp_dir)

from .manager import ClipboardManager