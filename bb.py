import sys
import json
import asyncio
import psutil
import time
from aiohttp import web, ClientSession
from common import log_activity, get_clipboard_content, set_clipboard_content, get_clipboard_size

connected_websockets = set()
last_clipboard_content = None
PING_INTERVAL = 5
last_send = 0

async def watch_clipboard(on_change):
    global last_clipboard_content
    while True:
        current = get_clipboard_content()
        if current != last_clipboard_content and current is not None:
            last_clipboard_content = current
            await on_change(current)
        await asyncio.sleep(1)

async def handle_clipboard_message(data):
    global last_clipboard_content
    content = json.loads(data)
    if content and 'type' in content and 'data' in content and content != last_clipboard_content:
        set_clipboard_content(content['type'], content['data'])
        size = get_clipboard_size(content)
        log_activity(f"Received clipboard update ({content['type']}, {size})")
        last_clipboard_content = get_clipboard_content()

async def server_clipboard_watcher():
    async def broadcast(content):
        size = get_clipboard_size(content)
        log_activity(f"Clipboard changed ({content['type']}, {size}). Broadcasting.")
        message = json.dumps(content)
        for ws in list(connected_websockets):
            try:
                await ws.send_str(message)
            except:
                connected_websockets.discard(ws)
    await watch_clipboard(broadcast)

async def handle_server_ws(request):
    global last_clipboard_content
    ws = web.WebSocketResponse(heartbeat=PING_INTERVAL, receive_timeout=PING_INTERVAL*2)
    await ws.prepare(request)
    client_ip = request.remote
    log_activity(f"New client connected from {client_ip}")
    connected_websockets.add(ws)
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                await handle_clipboard_message(msg.data)
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

# faster detection of broken socket (aiohttp's websocket pings don't seem effective)
async def client_ping_task(ws):
    global last_send
    while True:
        if time.time() - last_send > PING_INTERVAL:
            log_activity("pinging")
            await ws.send_str(json.dumps({}))
            last_send = time.time()
        await asyncio.sleep(1)

async def client_clipboard_watcher(ws):
    global last_send
    async def send_to_server(content):
        global last_send
        await ws.send_str(json.dumps(content))
        last_send = time.time()
        size = get_clipboard_size(content)
        log_activity(f"Local clipboard changed ({content['type']}, {size}). Sending.")
    await watch_clipboard(send_to_server)

async def client_listener(ws):
    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            await handle_clipboard_message(msg.data)

async def start_client(url):
    log_activity(f"Connecting to {url}...")
    while True:
        try:
            async with ClientSession() as session:
                async with session.ws_connect(url, heartbeat=PING_INTERVAL, receive_timeout=PING_INTERVAL*2) as ws:
                    log_activity("Connected successfully. Watching clipboard...")
                    watcher_task = asyncio.create_task(client_clipboard_watcher(ws))
                    listener_task = asyncio.create_task(client_listener(ws))
                    ping_task = asyncio.create_task(client_ping_task(ws))
                    await asyncio.gather(watcher_task, listener_task, ping_task)
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