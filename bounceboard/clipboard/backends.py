class ClipboardBackend:
    """Abstract clipboard backend."""

    def get_content(self):
        raise NotImplementedError

    def set_content(self, clipboard, temp_dir=None):
        raise NotImplementedError


class LinuxBackend(ClipboardBackend):
    def get_content(self):
        from .linux import get_content as _get
        return _get()

    def set_content(self, clipboard, temp_dir=None):
        from .linux import set_content as _set
        return _set(clipboard, temp_dir)


class MacOSBackend(ClipboardBackend):
    def get_content(self):
        from .macos import get_content as _get
        return _get()

    def set_content(self, clipboard, temp_dir=None):
        from .macos import set_content as _set
        return _set(clipboard, temp_dir)


class WindowsBackend(ClipboardBackend):
    def get_content(self):
        from .win import get_content as _get
        return _get()

    def set_content(self, clipboard, temp_dir=None):
        from .win import set_content as _set
        return _set(clipboard, temp_dir)


class PyperclipBackend(ClipboardBackend):
    def get_content(self):
        import pyperclip
        from .common import calculate_hash
        try:
            text = pyperclip.paste()
            if not text:
                return None
            data = text.encode("utf-8")
            return ({
                "type": "text/plain",
                "size": len(data),
                "hash": calculate_hash(data),
            }, data)
        except Exception:
            return None

    def set_content(self, clipboard, temp_dir=None):
        import pyperclip
        try:
            header, data = clipboard
            if header["type"] != "text/plain":
                import logging
                logging.warning(f"Falling back to text/plain for {header['type']}")
            pyperclip.copy(data.decode("utf-8"))
            return True
        except Exception:
            return False


BACKENDS = {
    "Linux": LinuxBackend,
    "Darwin": MacOSBackend,
    "Windows": WindowsBackend,
}


def get_backend(system):
    return BACKENDS.get(system, PyperclipBackend)()
