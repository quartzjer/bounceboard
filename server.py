#!/usr/bin/env python3
import asyncio
import websockets
import pyperclip
import socket
from datetime import datetime
import json
import base64
from PIL import ImageGrab
from io import BytesIO

connected_websockets = set()
last_clipboard_content = ""

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

def log_activity(message):
    """Print timestamped activity message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def get_clipboard_size(content):
    """Get human-readable size of clipboard content"""
    if content['type'] == 'image':
        size_bytes = len(base64.b64decode(content['data']))
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{len(content['data'])} chars"

def get_clipboard_content():
    """Get clipboard content, supporting both text and images"""
    try:
        # Try to get image from clipboard
        image = ImageGrab.grabclipboard()
        if image:
            buffer = BytesIO()
            image.save(buffer, format='PNG')
            img_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return {'type': 'image', 'data': img_data}
    except:
        pass
    
    # Fall back to text clipboard
    try:
        text = pyperclip.paste()
        return {'type': 'text', 'data': text}
    except:
        return {'type': 'text', 'data': ''}

def set_clipboard_content(content_type, data):
    """Set clipboard content based on type"""
    if content_type == 'image':
        image_data = base64.b64decode(data)
        image = Image.open(BytesIO(image_data))
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        ImageGrab.put(image)
    else:
        pyperclip.copy(data)

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
                last_clipboard_content = content
                set_clipboard_content(content['type'], content['data'])
                size = get_clipboard_size(content)
                log_activity(f"Received clipboard update from {client_ip} ({content['type']}, {size})")
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
