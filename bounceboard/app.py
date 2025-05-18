import logging
import sys
import json
import asyncio
import psutil
import time
import secrets
import base64
import argparse
import signal
import atexit
import shutil
import tempfile
import os
import ssl
import hashlib
from aiohttp import web, ClientSession
from .clipboard import ClipboardManager

# Shared clipboard manager instance
clipboard_manager = ClipboardManager()

connected_websockets = set()
pending_header = {}
PING_INTERVAL = 5
server_key = None
temp_dir = None
save_dir = None

def generate_key():
    random_bytes = secrets.token_bytes(5)
    encoded = base64.b32encode(random_bytes).decode('ascii')
    return encoded.lower()

def clipboard_bytes(data_bytes):
    if data_bytes is None:
        return "0 bytes"
    size_bytes = len(data_bytes)
    if size_bytes > 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    if size_bytes > 1024:
        return f"{size_bytes / 1024:.1f}KB"
    return f"{size_bytes} bytes"

def setup_logging(debug=False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

async def server_clipboard_watcher():
    async def broadcast(clipboard):
        header, data = clipboard
        logging.info(f"Clipboard change detected ({header['type']}, {clipboard_bytes(data)}). Broadcasting.")
        save_clipboard_update(header, data)
        for ws in list(connected_websockets):
            try:
                await ws.send_json(header)
                await ws.send_bytes(data)
            except:
                logging.exception(f"Error sending clipboard to client {id(ws)}")
                ws.close()
                connected_websockets.discard(ws)
    await clipboard_manager.watch(broadcast)

async def handle_server_ws(request):
    client_key = request.query.get('key')
    if not client_key or client_key != server_key:
        return web.Response(status=403, text='Invalid key')

    ws = web.WebSocketResponse(heartbeat=PING_INTERVAL, receive_timeout=PING_INTERVAL*2)
    await ws.prepare(request)
    client_ip = request.remote
    logging.info(f"New client connected from {client_ip}")
    connected_websockets.add(ws)
    try:
        current = await clipboard_manager.get_current()
        if current is not None:
            header, data = current
            await ws.send_json(header)
            await ws.send_bytes(data)
            logging.info(f"Sent current clipboard to new client ({header['type']}, {clipboard_bytes(data)})")

        async for msg in ws:
            logging.debug(f"Received message from client {client_ip}: {msg.type}")
            if msg.type == web.WSMsgType.TEXT:
                header = json.loads(msg.data)
                pending_header[id(ws)] = header
            elif msg.type == web.WSMsgType.BINARY and id(ws) in pending_header:
                header = pending_header.pop(id(ws))
                incoming = (header, msg.data)
                if not header.get('hash'):
                    header['hash'] = hashlib.sha256(msg.data).hexdigest()
                if await clipboard_manager.apply_update(incoming):
                    save_clipboard_update(header, msg.data)
                    logging.info(f"Received clipboard update ({header['type']}, {clipboard_bytes(msg.data)})")
                # always relay out
                for other_ws in list(connected_websockets):
                    if other_ws != ws:
                        try:
                            await other_ws.send_json(header)
                            await other_ws.send_bytes(msg.data)
                        except Exception:
                            logging.exception(f"Error sending clipboard to client {id(other_ws)}")
                            connected_websockets.discard(other_ws)
                    
    finally:
        pending_header.pop(id(ws), None)
        connected_websockets.discard(ws)
        logging.info(f"Client {client_ip} disconnected")
    return ws

def get_ip_addresses():
    ips = []
    for _, addresses in psutil.net_if_addrs().items():
        for addr in addresses:
            if addr.family == 2:  # AF_INET (IPv4)
                if not addr.address.startswith('127.'):
                    ips.append(addr.address)
    return sorted(ips)

async def handle_index_page(request):
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return web.Response(text=html_content, content_type='text/html')

async def handle_favicon(request):
    return web.Response(status=204)

async def start_server(port, key):
    global server_key
    server_key = key if key else generate_key()
    app = web.Application()
    app.router.add_get('/', handle_index_page)
    app.router.add_get('/favicon.ico', handle_favicon)
    app.router.add_get('/ws/', handle_server_ws)
    
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain('cert.pem', 'key.pem')
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '', port, ssl_context=ssl_context)
    await site.start()
    
    asyncio.create_task(server_clipboard_watcher())
    print("\n=== Clipboard Sync Server ===")
    print(f"\nConnection URL(s):")
    for ip in get_ip_addresses():
        print(f"https://{ip}:{port}/?key={server_key}")
    logging.info("Server started and waiting for connections...")
    while True:
        await asyncio.sleep(3600)

async def client_clipboard_watcher(ws):
    async def send_to_server(clipboard):
        try:
            header, data = clipboard
            logging.info(f"Clipboard change detected ({header['type']}, {clipboard_bytes(data)}). Sending to server.")
            save_clipboard_update(header, data)
            await ws.send_json(header)
            await ws.send_bytes(data)
        except Exception:
            logging.exception("Error sending clipboard")
            raise
    await clipboard_manager.watch(send_to_server)

async def client_listener(ws):
    header = None
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                header = json.loads(msg.data)
            elif msg.type == web.WSMsgType.BINARY and header:
                incoming = (header, msg.data)
                if await clipboard_manager.apply_update(incoming):
                    save_clipboard_update(header, msg.data)
                    logging.info(f"Received clipboard update ({header['type']}, {clipboard_bytes(msg.data)})")
                header = None
    except Exception as e:
        logging.error(f"Client listener error: {e}")

async def start_client(url):
    if url.startswith('https://'):
        url = 'wss://' + url[8:]
        if '/?key=' in url:
            url = url.replace('/?key=', '/ws/?key=')
    logging.info(f"Connecting to {url}...")
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    while True:
        try:
            async with ClientSession() as session:
                async with session.ws_connect(
                    url,
                    heartbeat=PING_INTERVAL,
                    receive_timeout=PING_INTERVAL*2,
                    ssl=ssl_context
                ) as ws:
                    logging.info("Connected successfully. Watching clipboard...")
                    watcher_task = asyncio.create_task(client_clipboard_watcher(ws))
                    listener_task = asyncio.create_task(client_listener(ws))
                    try:
                        await asyncio.gather(watcher_task, listener_task)
                    finally:
                        watcher_task.cancel()
                        listener_task.cancel()
                        await asyncio.gather(watcher_task, listener_task, return_exceptions=True) # Ensure tasks are fully cancelled
        except Exception as e:
            logging.info(f"Connection failed, retrying in 5s: {str(e)}")
            await asyncio.sleep(5)

def parse_args():
    parser = argparse.ArgumentParser(description='Clipboard synchronization server/client')
    parser.add_argument('-v', '--verbose', action='store_true', help='enable debug logging')
    parser.add_argument('--version', action='store_true', help='show version and exit')
    parser.add_argument('-x', '--xclip-alt', action='store_true', help='enable xclip -alt-text support (Linux only, see README)')
    parser.add_argument('--save', metavar='DIR', help='save clipboard history to specified directory')
    subparsers = parser.add_subparsers(dest='mode', help='operating mode')
    
    server_parser = subparsers.add_parser('server', help='run in server mode')
    server_parser.add_argument('-p', '--port', type=int, default=4444,
                             help='port to listen on (default: 4444)')
    server_parser.add_argument('-k', '--key', help='custom access key (default: auto-generated)')
    
    client_parser = subparsers.add_parser('client', help='run in client mode')
    client_parser.add_argument('url', help='server URL with key (https://host:port/?key=access_key)')
    
    args = parser.parse_args()
    if args.version:
        from . import __version__
        print(f"bounceboard version {__version__}")
        sys.exit(0)

    if not args.mode:
        parser.print_help()
        sys.exit(1)
    return args

def save_clipboard_update(header, data):
    if not save_dir:
        return
        
    header = header.copy()
    header['time'] = time.time()
    
    day_dir = os.path.join(save_dir, time.strftime('%Y-%m-%d'))
    os.makedirs(day_dir, exist_ok=True)
    
    base_name = header['hash']
    with open(os.path.join(day_dir, f"{base_name}.json"), 'w') as f:
        json.dump(header, f)
    with open(os.path.join(day_dir, f"{base_name}.bin"), 'wb') as f:
        f.write(data)

def init_temp_dir():
    global temp_dir
    temp_dir = tempfile.mkdtemp(prefix='bb_')

def cleanup():
    global temp_dir
    if temp_dir and os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

def signal_handler(signum, frame):
    logging.info("Received interrupt signal, shutting down...")
    for ws in connected_websockets:
        try:
            ws.force_close()
        except:
            pass
    cleanup()
    sys.exit(0)

def main():
    args = parse_args()
    setup_logging(args.verbose)
    
    global save_dir
    if args.save:
        save_dir = os.path.abspath(args.save)
        os.makedirs(save_dir, exist_ok=True)
        logging.info(f"Saving clipboard history to {save_dir}")
    
    if args.xclip_alt:
        os.environ['BB_XCLIP_ALT'] = '1'
    
    init_temp_dir()
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, signal_handler)
    
    if args.mode == 'client':
        if "?key=" not in args.url:
            print("Error: URL must include the key parameter (e.g., ws://host:port/?key=abcd1234)")
            sys.exit(1)
        try:
            asyncio.run(start_client(args.url))
        except SystemExit:
            pass
    else:
        asyncio.run(start_server(args.port, args.key))

if __name__ == "__main__":
    main()