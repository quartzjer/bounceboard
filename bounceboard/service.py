import asyncio
import logging
import ssl
import time
from aiohttp import web, ClientSession

from .clipboard import ClipboardManager
from .sync import ClipboardConnection
from .app import clipboard_bytes, save_clipboard_update, generate_key, get_ip_addresses

PING_INTERVAL = 5
clipboard_manager = ClipboardManager()


class ClipboardServer:
    def __init__(self, port=4444, key=None):
        self.port = port
        self.key = key or generate_key()
        self._connections = set()

    async def _broadcast(self, clipboard):
        for conn in set(self._connections):
            try:
                await conn.send(clipboard)
            except Exception:
                logging.exception("Error sending to client")
                self._connections.discard(conn)

    async def _watch_clipboard(self):
        async def on_change(clipboard):
            header, data = clipboard
            logging.info(
                "Clipboard change detected (%s, %s). Broadcasting.",
                header["type"],
                clipboard_bytes(data),
            )
            save_clipboard_update(header, data)
            await self._broadcast(clipboard)

        await clipboard_manager.watch(on_change)

    async def _ws_handler(self, request):
        if request.query.get("key") != self.key:
            return web.Response(status=403, text="Invalid key")

        ws = web.WebSocketResponse(heartbeat=PING_INTERVAL, receive_timeout=PING_INTERVAL * 2)
        await ws.prepare(request)
        conn = ClipboardConnection(ws)
        self._connections.add(conn)
        client_ip = request.remote
        logging.info("New client connected from %s", client_ip)

        current = await clipboard_manager.get_current()
        if current:
            await conn.send(current)
            header, data = current
            logging.info(
                "Sent current clipboard to new client (%s, %s)",
                header["type"],
                clipboard_bytes(data),
            )

        try:
            async for clipboard in conn:
                if await clipboard_manager.apply_update(clipboard):
                    save_clipboard_update(*clipboard)
                    header, data = clipboard
                    logging.info(
                        "Received clipboard update (%s, %s)",
                        header["type"],
                        clipboard_bytes(data),
                    )
                for other in set(self._connections):
                    if other is not conn:
                        try:
                            await other.send(clipboard)
                        except Exception:
                            logging.exception("Error sending to client")
                            self._connections.discard(other)
        finally:
            self._connections.discard(conn)
            logging.info("Client %s disconnected", client_ip)

        return ws

    async def start(self):
        app = web.Application()
        app.router.add_get("/ws/", self._ws_handler)

        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain("cert.pem", "key.pem")

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "", self.port, ssl_context=ssl_context)
        await site.start()

        asyncio.create_task(self._watch_clipboard())

        print("\n=== Clipboard Sync Server ===")
        print("\nConnection URL(s):")
        for ip in get_ip_addresses():
            print(f"https://{ip}:{self.port}/?key={self.key}")
        logging.info("Server started and waiting for connections...")
        while True:
            await asyncio.sleep(3600)


class ClipboardClient:
    def __init__(self, url: str):
        if url.startswith("https://"):
            url = "wss://" + url[8:]
            if "/?key=" in url:
                url = url.replace("/?key=", "/ws/?key=")
        self.url = url

    async def _watch_clipboard(self, conn):
        async def send_change(clipboard):
            header, data = clipboard
            logging.info(
                "Clipboard change detected (%s, %s). Sending to server.",
                header["type"],
                clipboard_bytes(data),
            )
            save_clipboard_update(header, data)
            await conn.send(clipboard)

        await clipboard_manager.watch(send_change)

    async def _listener(self, conn):
        async for clipboard in conn:
            if await clipboard_manager.apply_update(clipboard):
                save_clipboard_update(*clipboard)
                header, data = clipboard
                logging.info(
                    "Received clipboard update (%s, %s)",
                    header["type"],
                    clipboard_bytes(data),
                )

    async def start(self):
        logging.info("Connecting to %s...", self.url)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        while True:
            try:
                async with ClientSession() as session:
                    async with session.ws_connect(
                        self.url,
                        heartbeat=PING_INTERVAL,
                        receive_timeout=PING_INTERVAL * 2,
                        ssl=ssl_context,
                    ) as ws:
                        logging.info("Connected successfully. Watching clipboard...")
                        conn = ClipboardConnection(ws)
                        watcher = asyncio.create_task(self._watch_clipboard(conn))
                        listener = asyncio.create_task(self._listener(conn))
                        try:
                            await asyncio.gather(watcher, listener)
                        finally:
                            watcher.cancel()
                            listener.cancel()
                            await asyncio.gather(watcher, listener, return_exceptions=True)
            except Exception as e:
                logging.info("Connection failed, retrying in 5s: %s", e)
                await asyncio.sleep(5)

