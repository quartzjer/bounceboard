import pyperclip
import base64
import platform
import subprocess
import tempfile
import os
from datetime import datetime

# MIME types in order of preference
MIME_ORDER = ['image/png', 'text/html', 'text/rtf', 'text/plain']

MACOS_TYPE_TO_MIME = {
    '«class PNGf»': 'image/png',
    'GIF picture': 'image/gif',
    '«class RTF »': 'text/rtf',
    '«class HTML»': 'text/html',
    'string': 'text/plain',
}

MIME_TO_MACOS_TYPE = {mime: mac_type for mac_type, mime in MACOS_TYPE_TO_MIME.items()}

def log_activity(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def get_clipboard_size(content):
    if content is None:
        return "0 bytes"
    size_bytes = len(base64.b64decode(content['data']))
    if content['type'] != 'text/plain':
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes} chars"

def _get_linux_mime_types():
    try:
        result = subprocess.run(['xclip', '-selection', 'clipboard', '-t', 'TARGETS', '-o'], capture_output=True, text=True)
        return result.stdout.strip().split('\n')
    except:
        return []

def _get_linux_clipboard():
    mime_types = _get_linux_mime_types()
    
    for mime_type in MIME_ORDER:
        if mime_type in mime_types:
            result = subprocess.run(['xclip', '-selection', 'clipboard', '-t', mime_type, '-o'], capture_output=True)
            if result.returncode == 0:
                return {'type': mime_type, 'data': base64.b64encode(result.stdout).decode('utf-8')}
    
    return None

def _get_macos_types():
    try:
        result = subprocess.run(['osascript', '-e', 'clipboard info'], capture_output=True, text=True)
        if result.returncode == 0:
            types = []
            items = [item.strip() for item in result.stdout.split(',')]
            for item in items:
                mac_type = item.strip()
                types.append(mac_type)
            return types
    except Exception as e:
        log_activity(f"Error getting macOS clipboard types: {str(e)}")
        return []
    return []

def _get_macos_clipboard():
    mac_types = _get_macos_types()
    
    for mime_type in MIME_ORDER:
        for mac_type, mime in MACOS_TYPE_TO_MIME.items():
            if mime_type == mime and mac_type in mac_types:
                result = subprocess.run(['osascript', '-e', f"the clipboard as {mac_type}"], capture_output=True, text=True)
                if result.returncode == 0:
                    output = result.stdout.strip()
                    # Check for «data XXXX<hex>» format
                    if output.startswith('«data ') and output.endswith('»'):
                        hex_data = output[10:-1]
                        binary_data = bytes.fromhex(hex_data)
                    else:
                        binary_data = output.encode('utf-8')
                    return {'type': mime_type, 'data': base64.b64encode(binary_data).decode('utf-8')}
    log_activity(f"Unsupported clipboard data types: {mac_types}")
    return None

def get_clipboard_content():
    system = platform.system()
    try:
        if system == "Linux":
            return _get_linux_clipboard()
        elif system == "Darwin":
            return _get_macos_clipboard()
        else:
            text = pyperclip.paste()
            return {'type': 'text/plain', 'data': base64.b64encode(text.encode('utf-8')).decode('utf-8')}
    except Exception as e:
        log_activity(f"Error getting clipboard content: {str(e)}")
        return None

def _set_linux_clipboard(content_type, data):
    if content_type == 'text/plain':
        content_type = 'STRING' # override text/plain with STRING for compatibility
    process = subprocess.Popen(['xclip', '-selection', 'clipboard', '-t', content_type, '-i'], stdin=subprocess.PIPE)
    process.communicate(input=data)

def _set_macos_clipboard(content_type, data):
    mac_type = MIME_TO_MACOS_TYPE.get(content_type)
    if not mac_type:
        log_activity(f"Unsupported content type for macOS: {content_type}")
        return
        
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    
    try:
        subprocess.run(['osascript', '-e', f'set the clipboard to (read (POSIX file "{tmp_path}") as {mac_type})'])
    finally:
        os.unlink(tmp_path)

def set_clipboard_content(content_type, data):
    system = platform.system()
    decoded = base64.b64decode(data)
    try:
        if system == "Linux":
            _set_linux_clipboard(content_type, decoded)
        elif system == "Darwin":
            _set_macos_clipboard(content_type, decoded)
        else:
            if content_type != 'text/plain':
                log_activity(f"Error: Unsupported OS for {content_type} clipboard")
            else:
                pyperclip.copy(decoded.decode('utf-8'))
    except Exception as e:        log_activity(f"Error setting clipboard content: {str(e)}")