import sys
import json
import asyncio
import psutil
from aiohttp import web, ClientSession
from common import log_activity, get_clipboard_content, set_clipboard_content, get_clipboard_size

connected_websockets = set()
last_clipboard_content = None
PING_INTERVAL = 5

async def server_clipboard_watcher():
    global last_clipboard_content
    while True:
        current_content = get_clipboard_content()
        if current_content != last_clipboard_content and current_content is not None:
            last_clipboard_content = current_content
            size = get_clipboard_size(current_content)
            log_activity(f"Clipboard changed ({current_content['type']}, {size}). Broadcasting.")
            message = json.dumps(current_content)
            for ws in list(connected_websockets):
                try:
                    await ws.send_str(message)
                except:
                    connected_websockets.discard(ws)
        await asyncio.sleep(1)

async def handle_server_ws(request):
    global last_clipboard_content
    ws = web.WebSocketResponse(heartbeat=PING_INTERVAL)
    await ws.prepare(request)
    client_ip = request.remote
    log_activity(f"New client connected from {client_ip}")
    connected_websockets.add(ws)
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                content = json.loads(msg.data)
                if content != last_clipboard_content:
                    set_clipboard_content(content['type'], content['data'])
                    size = get_clipboard_size(content)
                    log_activity(f"Received clipboard update ({content['type']}, {size})")
                    last_clipboard_content = get_clipboard_content()
    finally:
        connected_websockets.discard(ws)
        log_activity(f"Client {client_ip} disconnected")
    return ws

def get_ip_addresses():
    ips = []
    for interface, addresses in psutil.net_if_addrs().items():
        for addr in addresses:
            if addr.family == 2:  # AF_INET (IPv4)
                if not addr.address.startswith('127.'):
                    ips.append(addr.address)
    return sorted(ips)

async def start_server(port):
    app = web.Application()
    app.router.add_get('/', handle_server_ws)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '', port)
    await site.start()
    asyncio.create_task(server_clipboard_watcher())
    print("\n=== Clipboard Sync Server ===")
    print(f"\nConnection URLs:")
    for ip in get_ip_addresses():
        print(f"ws://{ip}:{port}")
    print("\nWaiting for connections...\n")
    while True:
        await asyncio.sleep(3600)

async def client_clipboard_watcher(ws):
    global last_clipboard_content
    while True:
        current_content = get_clipboard_content()
        if current_content != last_clipboard_content and current_content is not None:
            last_clipboard_content = current_content
            await ws.send_str(json.dumps(current_content))
            size = get_clipboard_size(current_content)
            log_activity(f"Local clipboard changed ({current_content['type']}, {size}). Sending.")
        await asyncio.sleep(1)

async def client_listener(ws):
    global last_clipboard_content
    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            content = json.loads(msg.data)
            if content != last_clipboard_content:
                set_clipboard_content(content['type'], content['data'])
                size = get_clipboard_size(content)
                log_activity(f"Received clipboard update ({content['type']}, {size})")
                last_clipboard_content = get_clipboard_content()

async def start_client(url):
    log_activity(f"Connecting to {url}...")
    while True:
        try:
            async with ClientSession() as session:
                async with session.ws_connect(url, heartbeat=PING_INTERVAL) as ws:
                    log_activity("Connected successfully. Watching clipboard...")
                    watcher_task = asyncio.create_task(client_clipboard_watcher(ws))
                    listener_task = asyncio.create_task(client_listener(ws))
                    await asyncio.gather(watcher_task, listener_task)
        except Exception as e:
            log_activity(f"Connection failed, retry in 5s... ({str(e)})")
            await asyncio.sleep(5)

def main():
    if len(sys.argv) > 1 and sys.argv[1].startswith("ws://"):
        url = sys.argv[1]
        asyncio.run(start_client(url))
    else:
        port = 4444
        if len(sys.argv) > 1:
            try:
                port = int(sys.argv[1])
            except:
                pass
        asyncio.run(start_server(port))

if __name__ == "__main__":
    main()