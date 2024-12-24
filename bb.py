import sys
import json
import asyncio
import psutil
import time
import secrets
import base64
import argparse
from aiohttp import web, ClientSession
from common import log_activity, get_clipboard_content, set_clipboard_content, get_clipboard_size

connected_websockets = set()
last_clipboard_content = None
PING_INTERVAL = 5
last_send = 0
server_key = None

def generate_key():
    random_bytes = secrets.token_bytes(5)
    encoded = base64.b32encode(random_bytes).decode('ascii')
    return encoded.lower()

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
        return content
    return None

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
                content = await handle_clipboard_message(msg.data)
                if content:  # If clipboard was updated, broadcast to other clients
                    message = json.dumps(content)
                    for other_ws in list(connected_websockets):
                        if other_ws != ws:
                            try:
                                await other_ws.send_str(message)
                            except:
                                connected_websockets.discard(other_ws)
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
        except web.WebSocketError as e:
            if "403" in str(e):
                log_activity("Authentication failed: Invalid key")
                return
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