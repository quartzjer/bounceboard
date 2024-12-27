import pyperclip
import platform
import subprocess
import tempfile
import os
import hashlib
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

last_temp_file = None

def log_activity(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def _get_linux_target(target_type):
    try:
        result = subprocess.run(['xclip', '-selection', 'clipboard', '-t', target_type, '-o'], 
                              capture_output=True)
        if result.returncode == 0:
            return result.stdout
        return None
    except:
        return None

def _handle_clipboard_file(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'rb') as f:
            data = f.read()
            return ({
                'type': 'application/x-file',
                'size': len(data),
                'name': os.path.basename(filepath),
                'hash': _calculate_hash(data)
            }, data)
    return None

def _write_temp_file(data, filename, temp_dir):
    global last_temp_file
    if last_temp_file and os.path.exists(last_temp_file):
        os.unlink(last_temp_file)
    last_temp_file = os.path.join(temp_dir, filename)
    with open(last_temp_file, 'wb') as tmp:
        tmp.write(data)
    return last_temp_file

def _calculate_hash(data):
    return hashlib.sha256(data).hexdigest()

def _get_linux_clipboard():
    result = _get_linux_target('TARGETS')
    mime_types = result.decode('utf-8').strip().split('\n') if result else []

    if 'text/uri-list' in mime_types:
        uri_data = _get_linux_target('text/uri-list')
        if uri_data:
            uri = uri_data.decode('utf-8').strip()
            if uri.startswith('file:///'):
                return _handle_clipboard_file(uri[7:])
                
    for mime_type in MIME_ORDER:
        if mime_type in mime_types:
            data = _get_linux_target(mime_type)
            if data is not None:
                header = {
                    'type': mime_type, 
                    'size': len(data),
                    'hash': _calculate_hash(data)
                }
                if mime_type != 'text/plain' and 'text/plain' in mime_types:
                    header['text'] = _get_linux_target('text/plain').decode('utf-8')
                return (header, data)
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

def _get_macos_target(mac_type):
    try:
        result = subprocess.run(['osascript', '-e', f"the clipboard as {mac_type}"], capture_output=True, text=True)
        if result.returncode == 0:
            output = result.stdout.strip()
            # Check for «data XXXX<hex>» format
            if output.startswith('«data ') and output.endswith('»'):
                return bytes.fromhex(output[10:-1])
            return output.encode('utf-8')
        return None
    except Exception as e:
        log_activity(f"Error getting macOS clipboard content: {str(e)}")
        return None

def _get_macos_clipboard():
    mac_types = _get_macos_types()

    if '«class furl»' in mac_types:
        try:
            result = subprocess.run(['osascript', '-e', 'POSIX path of (the clipboard as «class furl»)'], capture_output=True, text=True)
            if result.returncode == 0:
                return _handle_clipboard_file(result.stdout.strip())
        except Exception as e:
            log_activity(f"Error reading file from macOS clipboard: {str(e)}")
    
    for mime_type in MIME_ORDER:
        for mac_type, mime in MACOS_TYPE_TO_MIME.items():
            if mime_type == mime and mac_type in mac_types:
                data = _get_macos_target(mac_type)
                if data is not None:
                    header = {
                        'type': mime_type, 
                        'size': len(data),
                        'hash': _calculate_hash(data)
                    }
                    if mime_type != 'text/plain' and 'string' in mac_types:
                        text_data = _get_macos_target('string')
                        if text_data:
                            header['text'] = text_data.decode('utf-8')
                    return (header, data)
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
            data = text.encode('utf-8')
            return ({
                'type': 'text/plain', 
                'size': len(data),
                'hash': _calculate_hash(data)
            }, data)
    except Exception as e:
        log_activity(f"Error getting clipboard content: {str(e)}")
        return None

def _set_linux_clipboard(clipboard, temp_dir):
    header, data = clipboard
    if header['type'] == 'application/x-file':
        temp_path = _write_temp_file(data, header['name'], temp_dir)
        uri = f"file://{temp_path}\n"
        header = {'type': 'text/uri-list'}
        data = uri.encode('utf-8')

    content_type = header['type']
    if content_type == 'text/plain':
        content_type = 'STRING'  # override text/plain with STRING for compatibility
    process = subprocess.Popen(['xclip', '-selection', 'clipboard', '-t', content_type, '-i'], 
                             stdin=subprocess.PIPE)
    process.communicate(input=data)

def _set_macos_clipboard(clipboard, temp_dir):
    header, data = clipboard
    
    if header['type'] == 'application/x-file':
        temp_path = _write_temp_file(data, header['name'], temp_dir)
        subprocess.run(['osascript', '-e', f'set the clipboard to "{temp_path}" as «class furl»'])
        return

    mac_type = MIME_TO_MACOS_TYPE.get(header['type'])
    if not mac_type:
        log_activity(f"Unsupported content type for macOS: {header['type']}")
        return

    with tempfile.NamedTemporaryFile(delete=False, dir=temp_dir) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    
    try:
        subprocess.run(['osascript', '-e', f'set the clipboard to (read (POSIX file "{tmp_path}") as {mac_type})'])
    finally:
        os.unlink(tmp_path)

def set_clipboard_content(clipboard, temp_dir=None):
    system = platform.system()
    try:
        if system == "Linux":
            _set_linux_clipboard(clipboard, temp_dir)
        elif system == "Darwin":
            _set_macos_clipboard(clipboard, temp_dir)
        else:
            header, data = clipboard
            if header['type'] != 'text/plain':
                log_activity(f"Error: Unsupported OS for {header['type']} clipboard")
            else:
                pyperclip.copy(data.decode('utf-8'))
    except Exception as e:
        log_activity(f"Error setting clipboard content: {str(e)}")