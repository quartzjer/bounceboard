# bounceboard

Bounceboard is a simple clipboard synchronization tool that allows you to share clipboard content between multiple devices over a WebSocket connection.

Currently supports:
- MacOS & Linux
- Plain text
- Images (PNG)
- HTML
- Rich Text

Planned:
- File support
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

To sync clipboards, use the consolidated script:

### Server
```sh
python bb.py 4444
```
(Defaults to port 4444 if none given.)

### Client
```sh
python bb.py ws://<server_ip>:4444
```
Replace <server_ip> with the host running the server.

## How It Works

- The server monitors the clipboard for changes and broadcasts the new content to all connected clients.
- The client monitors the local clipboard for changes and sends the new content to the server.
- Both the server and client update their local clipboard when they receive new content from the other side.

## License

This project is licensed under the MIT License.
