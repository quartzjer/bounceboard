# bounceboard

Bounceboard is a full featured clipboard synchronization tool that allows you to share clipboard content between multiple devices over a network.

Currently supports:
- MacOS & Linux
- Plain text
- Images (PNG)
- HTML
- Rich Text
- File support

## Installation

Install from PyPI:
```sh
pip install bounceboard
```

## Usage

The tool can run in either server or client mode:

### Server Mode
```sh
bb server [-p PORT] [-k KEY]
```
Options:
- `-p`, `--port`: Port to listen on (default: 4444)
- `-k`, `--key`: Custom access key (default: auto-generated)

The server will display connection URLs with the access key when started.

### Client Mode
```sh
bb client ws://<server_ip>:<port>/?key=<access_key>
```
Replace `<server_ip>`, `<port>`, and `<access_key>` with the connection details provided by the server.

Multiple clients can be connected to a server, changes from any client will propogate to all.

### Additional Options
- `-v`, `--version`: Show version and exit
- `-x`, `--xclip-alt`: Enable xclip alternative text support (see Linux below)

## How It Works

- The server monitors its local clipboard for changes and broadcasts the new content to all connected clients.
- The client also monitors its local clipboard for changes and sends the new content to the server.
- Both the server and client update their local clipboard when they receive new content from the other side.
- Multiple clients are supported and all kept in sync (server relays).

## Platform Specifics

### Linux

You'll need `[xclip](https://github.com/astrand/xclip)` installed (available on all major platforms). The current version (0.13) only supports setting one target type, so for compatibility any incoming HTML or RTF is downconverted to just STRING.

If you want rich text sync support you can use this [PR](https://github.com/astrand/xclip/pull/142) and the `bb -x ...` flag to enable it.

## Protocol

The WebSocket protocol uses a simple and efficient two-part message exchange:

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

## ChangeLog

- v0.1.0: Initial release

## License

This project is licensed under the MIT License.
