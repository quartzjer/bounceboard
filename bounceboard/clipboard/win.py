import subprocess
import json
import logging
import tempfile
import os
from .common import (
    MIME_ORDER,
    calculate_hash,
    write_temp_file,
    handle_clipboard_file
)

# Windows clipboard format to MIME type mapping
FORMAT_TO_MIME = {
    'PNG': 'image/png',
    'HTML Format': 'text/html',
    'Rich Text Format': 'text/rtf',
    'UnicodeText': 'text/plain',
    'FileDropList': 'application/x-file'
}

MIME_TO_FORMAT = {mime: fmt for fmt, mime in FORMAT_TO_MIME.items()}

def _get_windows_formats():
    try:
        script = '''
        Add-Type -AssemblyName System.Windows.Forms
        $formats = [System.Windows.Forms.Clipboard]::GetDataObject().GetFormats()
        ConvertTo-Json @($formats)
        '''
        result = subprocess.run(['powershell', '-Command', script],
                              capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception:
        logging.exception("Error getting Windows clipboard formats")
    return []

def _get_windows_target(format_name):
    try:
        if format_name == 'FileDropList':
            script = '''
            Add-Type -AssemblyName System.Windows.Forms
            $data = [System.Windows.Forms.Clipboard]::GetDataObject()
            $files = $data.GetFileDropList()
            ConvertTo-Json @($files)
            '''
            result = subprocess.run(['powershell', '-Command', script],
                                capture_output=True, text=True)
            if result.returncode == 0:
                return json.loads(result.stdout)
            return None

        script = f'''
        Add-Type -AssemblyName System.Windows.Forms
        $data = [System.Windows.Forms.Clipboard]::GetDataObject()
        $content = $data.GetData("{format_name}")
        
        if ($content -is [System.IO.MemoryStream]) {{
            $bytes = [byte[]]::new($content.Length)
            $content.Position = 0
            $content.Read($bytes, 0, $content.Length)
            [System.BitConverter]::ToString($bytes) -replace '-',''
        }} else {{
            $content
        }}
        '''
        
        result = subprocess.run(['powershell', '-Command', script],
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            data = result.stdout.strip()
            if format_name in ['PNG', 'Rich Text Format']:
                return bytes.fromhex(data)
            return data
            
    except Exception:
        logging.exception(f"Error getting Windows clipboard content for format: {format_name}")
    return None

def get_content():
    formats = _get_windows_formats()
    
    # Handle file drops first
    if 'FileDropList' in formats:
        files = _get_windows_target('FileDropList')
        if files and len(files) > 0:
            return handle_clipboard_file(files[0])
    
    # Then handle other formats in preferred order
    for mime_type in MIME_ORDER:
        win_format = MIME_TO_FORMAT.get(mime_type)
        if win_format in formats:
            data = _get_windows_target(win_format)
            if data is not None:
                if isinstance(data, str):
                    data = data.encode('utf-8')
                
                header = {
                    'type': mime_type,
                    'size': len(data),
                    'hash': calculate_hash(data)
                }
                
                # Add plain text version for non-text formats
                if mime_type != 'text/plain' and 'UnicodeText' in formats:
                    text_data = _get_windows_target('UnicodeText')
                    if text_data:
                        header['text'] = text_data
                
                return (header, data)
    
    if formats:
        logging.error(f"Unsupported clipboard formats: {formats}")
    return None

def set_content(clipboard, temp_dir=None):
    header, data = clipboard
    
    if header['type'] == 'application/x-file':
        temp_path = write_temp_file(data, header['text'], temp_dir)
        script = f'''
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.Clipboard]::SetFileDropList([System.Collections.Specialized.StringCollection]@('{temp_path}'))
        '''
        result = subprocess.run(['powershell', '-Command', script])
        return result.returncode == 0

    win_format = MIME_TO_FORMAT.get(header['type'])
    if not win_format:
        logging.error(f"Unsupported content type for Windows: {header['type']}")
        return False

    try:
        # Write data to temp file for PowerShell to read
        with tempfile.NamedTemporaryFile(delete=False, dir=temp_dir) as tmp:
            tmp.write(data)
            data_path = tmp.name

        # Write alternate text to temp file if available
        text_path = None
        if 'text' in header:
            with tempfile.NamedTemporaryFile(delete=False, dir=temp_dir) as tmp:
                tmp.write(header['text'].encode('utf-8'))
                text_path = tmp.name

        script = f'''
        Add-Type -AssemblyName System.Windows.Forms
        $bytes = [System.IO.File]::ReadAllBytes('{data_path}')
        $ms = New-Object System.IO.MemoryStream
        $ms.Write($bytes, 0, $bytes.Length)
        $dataObj = New-Object System.Windows.Forms.DataObject
        '''

        if win_format in ['PNG', 'Rich Text Format']:
            script += f'''
            $ms.Position = 0
            $dataObj.SetData("{win_format}", $ms)
            '''
        else:
            script += f'''
            $content = [System.Text.Encoding]::UTF8.GetString($bytes)
            $dataObj.SetData("{win_format}", $content)
            '''

        if text_path:
            script += f'''
            $text = [System.IO.File]::ReadAllText('{text_path}')
            $dataObj.SetData("UnicodeText", $text)
            '''

        script += '''
        [System.Windows.Forms.Clipboard]::SetDataObject($dataObj, $true)
        '''

        result = subprocess.run(['powershell', '-Command', script])
        return result.returncode == 0

    finally:
        if os.path.exists(data_path):
            os.unlink(data_path)
        if text_path and os.path.exists(text_path):
            os.unlink(text_path)
