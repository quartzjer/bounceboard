
import pyperclip
import base64
import platform
import subprocess
from datetime import datetime
from PIL import ImageGrab
from io import BytesIO

def log_activity(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def get_clipboard_size(content):
    if content['type'] == 'image':
        size_bytes = len(base64.b64decode(content['data']))
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{len(content['data'])} chars"

def get_clipboard_content():
    try:
        image = ImageGrab.grabclipboard()
        if image:
            buffer = BytesIO()
            image.save(buffer, format='PNG')
            img_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return {'type': 'image', 'data': img_data}
    except:
        pass
    try:
        text = pyperclip.paste()
        return {'type': 'text', 'data': text}
    except:
        return {'type': 'text', 'data': ''}

def set_clipboard_content(content_type, data):
    if content_type == 'image':
        image_data = base64.b64decode(data)
        system = platform.system()
        if system == "Linux":
            process = subprocess.Popen(["xclip", "-selection", "clipboard", "-t", "image/png"], 
                                       stdin=subprocess.PIPE)
            process.communicate(input=image_data)
        elif system == "Darwin":
            process = subprocess.Popen(["pbcopy", "-Prefer", "png"], 
                                       stdin=subprocess.PIPE)
            process.communicate(input=image_data)
        else:
            log_activity("Error: Unsupported OS for image clipboard")
    else:
        pyperclip.copy(data)