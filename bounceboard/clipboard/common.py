import hashlib
import os
import logging

# MIME types in order of preference
MIME_ORDER = ['image/png', 'text/html', 'text/rtf', 'text/plain']

# Track last temp file for cleanup
last_temp_file = None

def calculate_hash(data):
    return hashlib.sha256(data).hexdigest()

def write_temp_file(data, filename, temp_dir):
    global last_temp_file
    if last_temp_file and os.path.exists(last_temp_file):
        os.unlink(last_temp_file)
    last_temp_file = os.path.join(temp_dir, filename)
    with open(last_temp_file, 'wb') as tmp:
        tmp.write(data)
    return last_temp_file

def handle_clipboard_file(filepath, filename=None):
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
            return ({
                'type': 'application/x-file',
                'size': len(data),
                'text': filename or os.path.basename(filepath),
                'hash': calculate_hash(data)
            }, data)
    except Exception:
        logging.exception(f"Error handling clipboard file: {filepath}")
        return None