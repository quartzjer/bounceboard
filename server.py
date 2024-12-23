#!/usr/bin/env python3
import asyncio
import websockets
import socket
import json
from common import log_activity, get_clipboard_content, set_clipboard_content, get_clipboard_size

connected_websockets = set()
last_clipboard_content = None

def get_ip_addresses():
    """Get all available IP addresses for the machine"""
    hostname = socket.gethostname()
    ips = []
    
    # Get local IP
    try:
        local_ip = socket.gethostbyname(hostname)
        ips.append(local_ip)
    except:
        pass
    
    # Get all network interface IPs
    try:
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if ip not in ips:
                ips.append(ip)
    except:
        pass
    
    return ips

async def clipboard_watcher():
    global last_clipboard_content
    while True:
        current_content = get_clipboard_content()
        if current_content != last_clipboard_content:
            last_clipboard_content = current_content
            size = get_clipboard_size(current_content)
            log_activity(f"Clipboard changed ({current_content['type']}, {size}). Broadcasting to {len(connected_websockets)} clients")
            message = json.dumps(current_content)
            for ws in connected_websockets.copy():
                try:
                    await ws.send(message)
                except websockets.exceptions.ConnectionClosed:
                    connected_websockets.discard(ws)
                    log_activity(f"Client disconnected. {len(connected_websockets)} clients remaining")
        await asyncio.sleep(1)

async def handler(websocket):
    global last_clipboard_content
    client_ip = websocket.remote_address[0]
    log_activity(f"New client connected from {client_ip}")
    connected_websockets.add(websocket)
    try:
        async for message in websocket:
            content = json.loads(message)
            if content != last_clipboard_content:
                set_clipboard_content(content['type'], content['data'])
                size = get_clipboard_size(content)
                log_activity(f"Received clipboard update from {client_ip} ({content['type']}, {size})")
                last_clipboard_content = get_clipboard_content()
    finally:
        connected_websockets.discard(websocket)
        log_activity(f"Client {client_ip} disconnected")

async def main():
    port = 4444
    print("\n=== Clipboard Sync Server ===")
    print(f"Starting server on port {port}...")
    
    # Print connection URLs
    print("\nConnection URLs:")
    for ip in get_ip_addresses():
        print(f"ws://{ip}:{port}")
    
    print("\nWaiting for connections...\n")
    
    async with websockets.serve(handler, "", port):
        # Run the clipboard watcher indefinitely
        await clipboard_watcher()

if __name__ == "__main__":
    asyncio.run(main())
