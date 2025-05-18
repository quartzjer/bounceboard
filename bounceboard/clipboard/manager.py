import asyncio
from . import get_content, set_content

class ClipboardManager:
    """Manage polling and caching of clipboard data."""

    def __init__(self, getter=get_content, setter=set_content):
        self._getter = getter
        self._setter = setter
        self._last_hash = None
        self._lock = asyncio.Lock()

    async def get_current(self):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._getter)

    async def set_clipboard(self, clipboard, temp_dir=None):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._setter, clipboard, temp_dir)

    def _is_cached(self, clipboard):
        if not clipboard:
            return False
        header, _ = clipboard
        return header.get("hash") == self._last_hash

    async def _cache(self, clipboard):
        if not clipboard:
            return False
        async with self._lock:
            header, _ = clipboard
            self._last_hash = header.get("hash")
            return True

    async def get_updated_clipboard(self):
        current = await self.get_current()
        if not self._is_cached(current):
            await self._cache(current)
            return current
        return None

    async def apply_update(self, clipboard, temp_dir=None):
        if not self._is_cached(clipboard):
            await self.set_clipboard(clipboard, temp_dir)
            await self._cache(clipboard)
            return True
        return False

    async def watch(self, on_change, interval=1):
        while True:
            current = await self.get_updated_clipboard()
            if current:
                await on_change(current)
            await asyncio.sleep(interval)
