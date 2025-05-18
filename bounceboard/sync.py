import json
import hashlib
import logging
from aiohttp import web


class ClipboardConnection:
    """Wrap websocket to send/receive clipboard payloads."""

    def __init__(self, ws: web.WebSocketResponse):
        self.ws = ws
        self._pending_header = None

    async def send(self, clipboard):
        header, data = clipboard
        await self.ws.send_json(header)
        await self.ws.send_bytes(data)

    async def __aiter__(self):
        async for msg in self.ws:
            if msg.type == web.WSMsgType.TEXT:
                self._pending_header = json.loads(msg.data)
            elif msg.type == web.WSMsgType.BINARY and self._pending_header:
                header = self._pending_header
                self._pending_header = None
                if not header.get("hash"):
                    header["hash"] = hashlib.sha256(msg.data).hexdigest()
                yield header, msg.data
            else:
                logging.debug("Unhandled websocket message: %s", msg.type)


