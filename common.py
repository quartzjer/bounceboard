import pyperclip
import base64
import platform
import subprocess
import tempfile
import os
from datetime import datetime

shown_pngpaste_warning = False

def log_activity(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def get_clipboard_size(content):
    if content['type'] == 'image':
        size_bytes = len(base64.b64decode(content['data']))
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{len(content['data'])} chars"

def _get_linux_mime_types():
    try:
        result = subprocess.run(['xclip', '-selection', 'clipboard', '-t', 'TARGETS', '-o'],
                              capture_output=True, text=True)
        return result.stdout.strip().split('\n')
    except:
        return []

def _get_linux_clipboard():
    mime_types = _get_linux_mime_types()
    
    if 'image/png' in mime_types:
        result = subprocess.run(['xclip', '-selection', 'clipboard', '-t', 'image/png', '-o'],
                              capture_output=True)
        if result.returncode == 0:
            return {'type': 'image', 'data': base64.b64encode(result.stdout).decode('utf-8')}
    
    if 'text/plain' in mime_types:
        result = subprocess.run(['xclip', '-selection', 'clipboard', '-t', 'text/plain', '-o'],
                              capture_output=True, text=True)
        if result.returncode == 0:
            return {'type': 'text', 'data': result.stdout}
    
    return {'type': 'text', 'data': ''}

def _get_macos_clipboard():
    global shown_pngpaste_warning
    try:
        result = subprocess.run(['pngpaste', '-b'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout:
            return {'type': 'image', 'data': result.stdout}
    except FileNotFoundError:
        if not shown_pngpaste_warning:
            log_activity("Warning: pngpaste not installed. Image clipboard support disabled. Install with: brew install pngpaste")
            shown_pngpaste_warning = True
    
    result = subprocess.run(['pbpaste'], capture_output=True, text=True)
    if result.returncode == 0:
        return {'type': 'text', 'data': result.stdout}
    
    return {'type': 'text', 'data': ''}

def get_clipboard_content():
    system = platform.system()
    try:
        if system == "Linux":
            return _get_linux_clipboard()
        elif system == "Darwin":
            return _get_macos_clipboard()
        else:
            # Fall back to pyperclip for unsupported systems
            text = pyperclip.paste()
            return {'type': 'text', 'data': text}
    except Exception as e:
        log_activity(f"Error getting clipboard content: {str(e)}")
        return {'type': 'text', 'data': ''}

def set_clipboard_content(content_type, data):
    if content_type == 'image':
        image_data = base64.b64decode(data)
        system = platform.system()
        if system == "Linux":
            process = subprocess.Popen(["wl-copy", "--type", "image/png"], 
                                       stdin=subprocess.PIPE)
            process.communicate(input=image_data)
        elif system == "Darwin":
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                tmp.write(image_data)
                tmp_path = tmp.name
            
            script = 'set the clipboard to (read (POSIX file "{}") as «class PNGf»)'.format(tmp_path)
            subprocess.run(['osascript', '-e', script])
            os.unlink(tmp_path)
        else:
            log_activity("Error: Unsupported OS for image clipboard")
    else:
        pyperclip.copy(data)