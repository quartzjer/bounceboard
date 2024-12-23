#!/usr/bin/env python3
import asyncio
import websockets
import pyperclip
import sys
from datetime import datetime

last_clipboard_content = None

def log_activity(message):
    """Print timestamped activity message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

async def clipboard_watcher(websocket):
    global last_clipboard_content
    while True:
        current_content = pyperclip.paste()
        if current_content != last_clipboard_content:
            last_clipboard_content = current_content
            await websocket.send(current_content)
            log_activity("Local clipboard changed. Sending to server")
        await asyncio.sleep(1)

async def listen_for_updates(websocket):
    global last_clipboard_content
    async for message in websocket:
        if message != last_clipboard_content:
            last_clipboard_content = message
            pyperclip.copy(message)
            log_activity("Received clipboard update from server")

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