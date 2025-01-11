import subprocess
import json
import os
import logging
import tempfile
from .common import (
    MIME_ORDER,
    calculate_hash,
    write_temp_file,
    handle_clipboard_file
)

UTI_TO_MIME = {
    'public.png': 'image/png',
    'com.compuserve.gif': 'image/gif',
    'public.rtf': 'text/rtf',
    'public.html': 'text/html',
    'public.utf8-plain-text': 'text/plain',
}

MIME_TO_UTI = {mime: uti for uti, mime in UTI_TO_MIME.items()}

def _get_macos_types():
    try:
        result = subprocess.run([
            'osascript', '-l', 'JavaScript', 
            '-e', 'ObjC.import("AppKit"); JSON.stringify(ObjC.deepUnwrap($.NSPasteboard.generalPasteboard.pasteboardItems.js[0].types))'
        ], capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout.strip())
    except Exception:
        logging.exception("Error getting macOS clipboard types")
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
    except Exception:
        logging.exception("Error getting macOS clipboard content")
        return None

def get_content():
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
                return handle_clipboard_file(file_path)
        except Exception:
            logging.exception("Error reading file URL from macOS clipboard")
            return None
    
    for mime_type in MIME_ORDER:
        for uti, mime in UTI_TO_MIME.items():
            if mime_type == mime and uti in utis:
                data = _get_macos_target(uti)
                if data is not None:
                    header = {
                        'type': mime_type, 
                        'size': len(data),
                        'hash': calculate_hash(data)
                    }
                    if mime_type != 'text/plain' and 'public.utf8-plain-text' in utis:
                        text_data = _get_macos_target('public.utf8-plain-text')
                        if text_data:
                            header['text'] = text_data.decode('utf-8')
                    return (header, data)
    if utis:
        logging.error(f"Unsupported clipboard data types: {utis}")
    return None

def set_content(clipboard, temp_dir=None):
    header, data = clipboard
    
    if header['type'] == 'application/x-file':
        temp_path = write_temp_file(data, header['text'], temp_dir)
        result = subprocess.run(['osascript', '-e', f'set the clipboard to "{temp_path}" as «class furl»'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"Error setting macOS clipboard file: {result.stderr}")
            return False
        return True

    uti = MIME_TO_UTI.get(header['type'])
    if not uti:
        logging.error(f"Unsupported content type for macOS: {header['type']}")
        return False

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
            logging.error(f"Error setting macOS clipboard content: {result.stderr}")
            return False
        return True
    finally:
        for path in temp_paths:
            os.unlink(path)
