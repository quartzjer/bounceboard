import sys
import json
import asyncio
import psutil
import time
import secrets
import base64
import argparse
from aiohttp import web, ClientSession
from common import log_activity, get_clipboard_content, set_clipboard_content

connected_websockets = set()
last_clipboard = None
pending_header = {}
PING_INTERVAL = 5
last_send = 0
server_key = None

def generate_key():
    random_bytes = secrets.token_bytes(5)
    encoded = base64.b32encode(random_bytes).decode('ascii')
    return encoded.lower()

def clipboard_bytes(data_bytes):
    if data_bytes is None:
        return "0 bytes"
    size_bytes = len(data_bytes)
    if size_bytes > 1024:
        return f"{size_bytes / 1024:.1f}KB"
    return f"{size_bytes} bytes"

async def watch_clipboard(on_change):
    global last_clipboard
    while True:
        current = get_clipboard_content()
        if current is not None and current != last_clipboard:
            last_clipboard = current
            await on_change(current)
        await asyncio.sleep(1)

async def server_clipboard_watcher():
    async def broadcast(clipboard):
        header, data = clipboard
        log_activity(f"Clipboard change detected ({header['type']}, {clipboard_bytes(data)}). Broadcasting.")
        for ws in list(connected_websockets):
            try:
                await ws.send_json(header)
                await ws.send_bytes(data)
            except:
                connected_websockets.discard(ws)
    await watch_clipboard(broadcast)

async def handle_server_ws(request):
    global last_clipboard
    client_key = request.query.get('key')
    if not client_key or client_key != server_key:
        return web.Response(status=403, text='Invalid key')

    ws = web.WebSocketResponse(heartbeat=PING_INTERVAL, receive_timeout=PING_INTERVAL*2)
    await ws.prepare(request)
    client_ip = request.remote
    log_activity(f"New client connected from {client_ip}")
    connected_websockets.add(ws)
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                header = json.loads(msg.data)
                pending_header[id(ws)] = header
            elif msg.type == web.WSMsgType.BINARY and id(ws) in pending_header:
                header = pending_header.pop(id(ws))
                current = (header, msg.data)
                if current != last_clipboard:
                    set_clipboard_content(current)
                    log_activity(f"Received clipboard update ({header['type']}, {clipboard_bytes(msg.data)})")
                    
                    # Broadcast to other clients
                    for other_ws in list(connected_websockets):
                        if other_ws != ws:
                            try:
                                await other_ws.send_json(header)
                                await other_ws.send_bytes(msg.data)
                            except:
                                connected_websockets.discard(other_ws)
                    
                    last_clipboard = current
    finally:
        pending_header.pop(id(ws), None)
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

async def start_server(port, key):
    global server_key
    server_key = key if key else generate_key()
    app = web.Application()
    app.router.add_get('/', handle_server_ws)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '', port)
    await site.start()
    asyncio.create_task(server_clipboard_watcher())
    print("\n=== Clipboard Sync Server ===")
    print(f"\nConnection URL(s):")
    for ip in get_ip_addresses():
        print(f"ws://{ip}:{port}/?key={server_key}")
    print("\nWaiting for connections...\n")
    while True:
        await asyncio.sleep(3600)

# faster detection of broken socket (aiohttp's websocket pings don't seem effective)
async def client_ping_task(ws):
    global last_send
    while True:
        if time.time() - last_send > PING_INTERVAL:
            await ws.send_str(json.dumps({}))
            last_send = time.time()
        await asyncio.sleep(1)

async def client_clipboard_watcher(ws):
    global last_send
    async def send_to_server(clipboard):
        global last_send
        header, data = clipboard
        await ws.send_json(header)
        await ws.send_bytes(data)
        last_send = time.time()
        log_activity(f"Local clipboard sync'd ({header['type']}, {clipboard_bytes(data)}). Sending.")
    await watch_clipboard(send_to_server)

async def client_listener(ws):
    header = None
    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            header = json.loads(msg.data)
        elif msg.type == web.WSMsgType.BINARY and header:
            set_clipboard_content((header, msg.data))
            log_activity(f"Received clipboard update ({header['type']}, {clipboard_bytes(msg.data)})")
            header = None

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

def parse_args():
    parser = argparse.ArgumentParser(description='Clipboard synchronization server/client')
    subparsers = parser.add_subparsers(dest='mode', help='operating mode')
    
    server_parser = subparsers.add_parser('server', help='run in server mode')
    server_parser.add_argument('-p', '--port', type=int, default=4444,
                             help='port to listen on (default: 4444)')
    server_parser.add_argument('-k', '--key', help='custom access key (default: auto-generated)')
    
    client_parser = subparsers.add_parser('client', help='run in client mode')
    client_parser.add_argument('url', help='server URL with key (ws://host:port/?key=access_key)')
    
    args = parser.parse_args()
    if not args.mode:
        parser.print_help()
        sys.exit(1)
    return args

def main():
    args = parse_args()
    if args.mode == 'client':
        if "?key=" not in args.url:
            print("Error: URL must include the key parameter (e.g., ws://host:port/?key=abcd1234)")
            sys.exit(1)
        asyncio.run(start_client(args.url))
    else:
        asyncio.run(start_server(args.port, args.key))

if __name__ == "__main__":
    main()