import platform
import logging
import pyperclip

from .common import calculate_hash
from .linux import get_content as _linux_get, set_content as _linux_set
from .macos import get_content as _macos_get, set_content as _macos_set
from .win import get_content as _win_get, set_content as _win_set

def _pyperclip_get():
    try:
        text = pyperclip.paste()
        if not text:
            return None
        data = text.encode('utf-8')
        return ({
            'type': 'text/plain', 
            'size': len(data),
            'hash': calculate_hash(data)
        }, data)
    except:
        return None

def _pyperclip_set(clipboard, temp_dir=None):
    try:
        header, data = clipboard
        if header['type'] != 'text/plain':
            logging.warning(f"Falling back to text/plain for {header['type']}")
        pyperclip.copy(data.decode('utf-8'))
        return True
    except:
        return False

def get_content():
    system = platform.system()
    try:
        if system == "Linux":
            result = _linux_get()
        elif system == "Darwin":
            result = _macos_get()
        elif system == "Windows":
            result = _win_get()
            
        if result is not None:
            return result
            
    except Exception:
        logging.exception(f"Native clipboard access failed for {system}, defaulting to text-only")
    
    return _pyperclip_get()

def set_content(clipboard, temp_dir=None):
    system = platform.system()
    try:
        if system == "Linux":
            if _linux_set(clipboard, temp_dir):
                return
        elif system == "Darwin":
            if _macos_set(clipboard, temp_dir):
                return
        elif system == "Windows":
            if _win_set(clipboard, temp_dir):
                return
    except Exception:
        logging.exception(f"Native clipboard access failed for {system}, defaulting to text-only")
    
    _pyperclip_set(clipboard, temp_dir)
