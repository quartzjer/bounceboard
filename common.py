import pyperclip
import platform
import subprocess
import tempfile
import os
import hashlib
from datetime import datetime
import json

# MIME types in order of preference
MIME_ORDER = ['image/png', 'text/html', 'text/rtf', 'text/plain']

UTI_TO_MIME = {
    'public.png': 'image/png',
    'com.compuserve.gif': 'image/gif',
    'public.rtf': 'text/rtf',
    'public.html': 'text/html',
    'public.utf8-plain-text': 'text/plain',
}

MIME_TO_UTI = {mime: uti for uti, mime in UTI_TO_MIME.items()}

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

def _handle_clipboard_file(filepath, filenme=None):
    with open(filepath, 'rb') as f:
        data = f.read()
        return ({
            'type': 'application/x-file',
            'size': len(data),
            'text': filenme or os.path.basename(filepath),
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
                if mime_type != 'text/plain' and 'STRING' in mime_types:
                    header['text'] = _get_linux_target('STRING').decode('utf-8')
                return (header, data)
    return None

def _get_macos_types():
    try:
        result = subprocess.run([
            'osascript', '-l', 'JavaScript', 
            '-e', 'ObjC.import("AppKit"); JSON.stringify(ObjC.deepUnwrap($.NSPasteboard.generalPasteboard.pasteboardItems.js[0].types))'
        ], capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout.strip())
    except Exception as e:
        log_activity(f"Error getting macOS clipboard types: {str(e)}")
        return []
    return []

def _get_macos_target(uti):
    try:
        script = f'''
        ObjC.import("AppKit");
        const pb = $.NSPasteboard.generalPasteboard;
        const data = pb.pasteboardItems.js[0].dataForType("{uti}");
        let hexString = "";
        for (let i = 0; i < data.length; i++) {{
            hexString += ("0" + data.bytes[i].toString(16)).slice(-2);
        }}
        hexString
        '''
        
        result = subprocess.run(['osascript', '-l', 'JavaScript', '-e', script], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            hex_data = result.stdout.strip()
            return bytes.fromhex(hex_data)
            
        return None
    except Exception as e:
        log_activity(f"Error getting macOS clipboard content: {str(e)}")
        return None

def _get_macos_clipboard():
    utis = _get_macos_types()

    if 'public.file-url' in utis:
        try:
            script = '''
            ObjC.import("AppKit");
            const pb = $.NSPasteboard.generalPasteboard;
            const item = pb.pasteboardItems.js[0];
            const data = item.dataForType("public.file-url");
            const str = $.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding);
            const url = $.NSURL.URLWithString(str);
            ObjC.unwrap(url.path);
            '''
            result = subprocess.run(['osascript', '-l', 'JavaScript', '-e', script],
                                 capture_output=True, text=True)
            if result.returncode == 0:
                file_path = result.stdout.strip()
                return _handle_clipboard_file(file_path)
        except Exception as e:
            log_activity(f"Error reading file URL from macOS clipboard: {str(e)}")
            return None
    
    for mime_type in MIME_ORDER:
        for uti, mime in UTI_TO_MIME.items():
            if mime_type == mime and uti in utis:
                data = _get_macos_target(uti)
                if data is not None:
                    header = {
                        'type': mime_type, 
                        'size': len(data),
                        'hash': _calculate_hash(data)
                    }
                    if mime_type != 'text/plain' and 'public.utf8-plain-text' in utis:
                        text_data = _get_macos_target('public.utf8-plain-text')
                        if text_data:
                            header['text'] = text_data.decode('utf-8')
                    return (header, data)
    if utis:
        log_activity(f"Unsupported clipboard data types: {utis}")
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
    content_type = header['type']
    text = header.get('text', None)
    if header['type'] == 'application/x-file':
        temp_path = _write_temp_file(data, text, temp_dir)
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

def _set_macos_clipboard(clipboard, temp_dir):
    header, data = clipboard
    
    if header['type'] == 'application/x-file':
        temp_path = _write_temp_file(data, header['text'], temp_dir)
        result = subprocess.run(['osascript', '-e', f'set the clipboard to "{temp_path}" as «class furl»'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            log_activity(f"Error setting macOS clipboard file: {result.stderr}")
        return

    uti = MIME_TO_UTI.get(header['type'])
    if not uti:
        log_activity(f"Unsupported content type for macOS: {header['type']}")
        return

    temp_paths = []
    try:
        with tempfile.NamedTemporaryFile(delete=False, dir=temp_dir) as tmp:
            tmp.write(data)
            temp_paths.append(tmp.name)
            
        text_path = None
        if 'text' in header:
            with tempfile.NamedTemporaryFile(delete=False, dir=temp_dir) as tmp:
                tmp.write(header['text'].encode('utf-8'))
                text_path = tmp.name
                temp_paths.append(text_path)
        
        script = f'''
        ObjC.import("AppKit");
        const pb = $.NSPasteboard.generalPasteboard;
        pb.clearContents;
        pb.setDataForType($.NSData.dataWithContentsOfFile("{temp_paths[0]}"), "{uti}");
        '''
        
        if text_path:
            script += f'''
        pb.setDataForType($.NSData.dataWithContentsOfFile("{text_path}"), "public.utf8-plain-text");
        '''
            
        result = subprocess.run(['osascript', '-l', 'JavaScript', '-e', script], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            log_activity(f"Error setting macOS clipboard content: {result.stderr}")
    finally:
        for path in temp_paths:
            os.unlink(path)

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