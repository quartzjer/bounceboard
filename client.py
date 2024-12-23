#!/usr/bin/env python3
import asyncio
import websockets
import pyperclip
import sys
from datetime import datetime
import json
import base64
from PIL import ImageGrab, Image
from io import BytesIO

last_clipboard_content = None

def log_activity(message):
    """Print timestamped activity message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

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

def get_clipboard_size(content):
    """Get human-readable size of clipboard content"""
    if content['type'] == 'image':
        size_bytes = len(base64.b64decode(content['data']))
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{len(content['data'])} chars"

async def clipboard_watcher(websocket):
    global last_clipboard_content
    while True:
        current_content = get_clipboard_content()
        if current_content != last_clipboard_content:
            last_clipboard_content = current_content
            await websocket.send(json.dumps(current_content))
            size = get_clipboard_size(current_content)
            log_activity(f"Local clipboard changed ({current_content['type']}, {size}). Sending to server")
        await asyncio.sleep(1)

async def listen_for_updates(websocket):
    global last_clipboard_content
    async for message in websocket:
        content = json.loads(message)
        if content != last_clipboard_content:
            last_clipboard_content = content
            set_clipboard_content(content['type'], content['data'])
            size = get_clipboard_size(content)
            log_activity(f"Received clipboard update from server ({content['type']}, {size})")

async def main(server_url):
    print("\n=== Clipboard Sync Client ===")
    print(f"Connecting to {server_url}...")
    
    try:
        async with websockets.connect(server_url) as ws:
            log_activity("Connected to server successfully")
            print("\nWatching clipboard for changes...\n")
            
            watcher_task = asyncio.create_task(clipboard_watcher(ws))
            listener_task = asyncio.create_task(listen_for_updates(ws))
            await asyncio.gather(watcher_task, listener_task)
    except (websockets.exceptions.ConnectionError, OSError) as e:
        print(f"\nError: Could not connect to {server_url}")
        print("Make sure the server is running and the URL is correct.")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"\nUsage: {sys.argv[0]} ws://<ip_or_hostname>:4444")
        print("Example: python client.py ws://192.168.1.100:4444")
        sys.exit(1)
    
    server_url = sys.argv[1]
    try:
        asyncio.run(main(server_url))
    except KeyboardInterrupt:
        print("\nClient stopped by user")