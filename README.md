# bounceboard

Bounceboard is a simple clipboard synchronization tool that allows you to share clipboard content between multiple devices over a WebSocket connection.

Currently supports:
- MacOS & Linux
- Plain text
- Images (PNG)
- HTML
- Rich Text
- File support

Planned:
- Easier install

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/bounceboard.git
    cd bounceboard
    ```

2. Install the required Python packages:
    ```sh
    pip install -r requirements.txt
    ```

## Usage

The tool can run in either server or client mode:

### Server Mode
```sh
python app.py server [-p PORT] [-k KEY]
```
Options:
- `-p`, `--port`: Port to listen on (default: 4444)
- `-k`, `--key`: Custom access key (default: auto-generated)

The server will display connection URLs with the access key when started.

### Client Mode
```sh
python app.py client ws://<server_ip>:<port>/?key=<access_key>
```
Replace `<server_ip>`, `<port>`, and `<access_key>` with the connection details provided by the server.

### Additional Options
- `-x`, `--xclip-alt`: Enable xclip alternative text support (Linux only)

## How It Works

- The server monitors the clipboard for changes and broadcasts the new content to all connected clients.
- The client monitors the local clipboard for changes and sends the new content to the server.
- Both the server and client update their local clipboard when they receive new content from the other side.
- Multiple clients are supported and all kept in sync.

## Protocol

The WebSocket protocol uses a simple two-part message exchange:

1. Header (JSON text message):
```json
{
    "type": "mime/type",    // Content MIME type (e.g., "text/plain", "image/png")
    "size": 1234,          // Content size in bytes
    "hash": "sha256...",   // SHA-256 hash of the content
    "text": "optional"     // Optional plain text representation
}
```

2. Binary message:
   - Contains the raw content bytes immediately following the header
   - Must be processed together with the preceding header

Supported MIME types:
- `text/plain`: Plain text content
- `text/html`: HTML content
- `text/rtf`: Rich Text Format
- `image/png`: PNG images
- `application/x-file`: File transfer (includes filename in header's text field)

Protocol flow:
1. Client connects with `?key=<access_key>` query parameter
2. Connection maintained with WebSocket ping/pong (5s interval)
3. Both sides send header+content pairs when clipboard changes
4. Both sides process incoming header+content pairs to update local clipboard

## License

This project is licensed under the MIT License.
