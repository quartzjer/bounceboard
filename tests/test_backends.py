import unittest
from unittest import mock

from bounceboard.clipboard import backends as cb_backends
import bounceboard.clipboard as clipboard


class DummyBackend(cb_backends.ClipboardBackend):
    def __init__(self):
        self.get_called = False
        self.set_called = False

    def get_content(self):
        self.get_called = True
        return ({'type': 'text/plain', 'size': 0, 'hash': '0'}, b'')

    def set_content(self, clipboard_item, temp_dir=None):
        self.set_called = True
        return True


class BackendTests(unittest.TestCase):
    def test_backend_selection(self):
        self.assertIsInstance(cb_backends.get_backend('Linux'), cb_backends.LinuxBackend)
        self.assertIsInstance(cb_backends.get_backend('Darwin'), cb_backends.MacOSBackend)
        self.assertIsInstance(cb_backends.get_backend('Windows'), cb_backends.WindowsBackend)
        self.assertIsInstance(cb_backends.get_backend('Other'), cb_backends.PyperclipBackend)

    def test_delegation(self):
        dummy = DummyBackend()
        with mock.patch.object(clipboard, '_backend', dummy), \
             mock.patch.object(clipboard, '_fallback', dummy):
            clipboard.get_content()
            clipboard.set_content(({'type': 'text/plain'}, b''))
        self.assertTrue(dummy.get_called)
        self.assertTrue(dummy.set_called)


if __name__ == '__main__':
    unittest.main()
