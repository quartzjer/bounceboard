import subprocess
import os
import logging
from .common import (
    MIME_ORDER,
    calculate_hash,
    write_temp_file,
    handle_clipboard_file
)

def _get_linux_target(target_type):
    try:
        result = subprocess.run(['xclip', '-selection', 'clipboard', '-t', target_type, '-o'], 
                              capture_output=True)
        if result.returncode == 0:
            return result.stdout
        return None
    except Exception as e:
        logging.info(f"Error reading clipboard target {target_type}: {e}")
        return None

def get_content():
    result = _get_linux_target('TARGETS')
    mime_types = result.decode('utf-8').strip().split('\n') if result else []

    if 'text/uri-list' in mime_types:
        uri_data = _get_linux_target('text/uri-list')
        if uri_data:
            uri = uri_data.decode('utf-8').strip()
            if uri.startswith('file:///'):
                return handle_clipboard_file(uri[7:])
                
    for mime_type in MIME_ORDER:
        if mime_type in mime_types:
            data = _get_linux_target(mime_type)
            if data is not None:
                header = {
                    'type': mime_type, 
                    'size': len(data),
                    'hash': calculate_hash(data)
                }
                if mime_type != 'text/plain' and 'STRING' in mime_types:
                    header['text'] = _get_linux_target('STRING').decode('utf-8')
                return (header, data)
    return None

def set_content(clipboard, temp_dir=None):
    header, data = clipboard
    content_type = header['type']
    text = header.get('text', None)
    if header['type'] == 'application/x-file':
        temp_path = write_temp_file(data, text, temp_dir)
        uri = f"file://{temp_path}\n"
        content_type = 'text/uri-list'
        data = uri.encode('utf-8')

    if bool(os.environ.get('BB_XCLIP_ALT')) and text:
        process = subprocess.Popen(['xclip', '-selection', 'clipboard', '-t', content_type, '-alt-text', text, '-i'], stdin=subprocess.PIPE)
    else:
        # xclip by default doesn't support alternate targets so we have to default all text-based ones to STRING
        if text:
            content_type = 'STRING'
            data = text.encode('utf-8')
        process = subprocess.Popen(['xclip', '-selection', 'clipboard', '-t', content_type, '-i'], 
                                stdin=subprocess.PIPE)
    process.communicate(input=data)
    return True
