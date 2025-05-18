import unittest
import asyncio

from bounceboard.clipboard.manager import ClipboardManager

class DummyBackend:
    def __init__(self):
        self.content = ({'type': 'text/plain', 'size': 0, 'hash': '0'}, b'')
    def get_content(self):
        return self.content
    def set_content(self, clipboard, temp_dir=None):
        self.content = clipboard
        return True

class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_updated_and_apply(self):
        backend = DummyBackend()
        mgr = ClipboardManager(backend.get_content, backend.set_content)

        first = await mgr.get_updated_clipboard()
        self.assertEqual(first, backend.content)

        # no change should return None
        self.assertIsNone(await mgr.get_updated_clipboard())

        new_clip = ({'type': 'text/plain', 'size': 1, 'hash': '1'}, b'a')
        await mgr.apply_update(new_clip)
        self.assertEqual(backend.content, new_clip)
        self.assertIsNone(await mgr.get_updated_clipboard())

if __name__ == '__main__':
    unittest.main()
