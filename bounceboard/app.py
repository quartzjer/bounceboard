import asyncio
import logging
import sys
import argparse
import signal
import atexit
import shutil
import tempfile
import os
import time

from .service import ClipboardServer, ClipboardClient


def generate_key():
    import secrets
    import base64

    random_bytes = secrets.token_bytes(5)
    encoded = base64.b32encode(random_bytes).decode("ascii")
    return encoded.lower()


def clipboard_bytes(data_bytes):
    if data_bytes is None:
        return "0 bytes"
    size_bytes = len(data_bytes)
    if size_bytes > 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    if size_bytes > 1024:
        return f"{size_bytes / 1024:.1f}KB"
    return f"{size_bytes} bytes"


def setup_logging(debug=False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_ip_addresses():
    import psutil

    ips = []
    for _, addresses in psutil.net_if_addrs().items():
        for addr in addresses:
            if addr.family == 2:  # AF_INET (IPv4)
                if not addr.address.startswith("127."):
                    ips.append(addr.address)
    return sorted(ips)


save_dir = None

def save_clipboard_update(header, data):
    if not save_dir:
        return

    header = header.copy()
    header["time"] = time.time()

    day_dir = os.path.join(save_dir, time.strftime("%Y-%m-%d"))
    os.makedirs(day_dir, exist_ok=True)

    base_name = header["hash"]
    with open(os.path.join(day_dir, f"{base_name}.json"), "w") as f:
        import json

        json.dump(header, f)
    with open(os.path.join(day_dir, f"{base_name}.bin"), "wb") as f:
        f.write(data)


temp_dir = None

def init_temp_dir():
    global temp_dir
    temp_dir = tempfile.mkdtemp(prefix="bb_")


def cleanup():
    global temp_dir
    if temp_dir and os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


def signal_handler(signum, frame):
    logging.info("Received interrupt signal, shutting down...")
    cleanup()
    sys.exit(0)


def parse_args():
    parser = argparse.ArgumentParser(description="Clipboard synchronization server/client")
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    parser.add_argument("--version", action="store_true", help="show version and exit")
    parser.add_argument(
        "-x",
        "--xclip-alt",
        action="store_true",
        help="enable xclip -alt-text support (Linux only, see README)",
    )
    parser.add_argument("--save", metavar="DIR", help="save clipboard history to specified directory")
    subparsers = parser.add_subparsers(dest="mode", help="operating mode")

    server_parser = subparsers.add_parser("server", help="run in server mode")
    server_parser.add_argument("-p", "--port", type=int, default=4444, help="port to listen on (default: 4444)")
    server_parser.add_argument("-k", "--key", help="custom access key (default: auto-generated)")

    client_parser = subparsers.add_parser("client", help="run in client mode")
    client_parser.add_argument("url", help="server URL with key (https://host:port/?key=access_key)")

    args = parser.parse_args()
    if args.version:
        from . import __version__

        print(f"bounceboard version {__version__}")
        sys.exit(0)

    if not args.mode:
        parser.print_help()
        sys.exit(1)
    return args


def main():
    args = parse_args()
    setup_logging(args.verbose)

    global save_dir
    if args.save:
        save_dir = os.path.abspath(args.save)
        os.makedirs(save_dir, exist_ok=True)
        logging.info(f"Saving clipboard history to {save_dir}")

    if args.xclip_alt:
        os.environ["BB_XCLIP_ALT"] = "1"

    init_temp_dir()
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, signal_handler)

    if args.mode == "client":
        if "?key=" not in args.url:
            print("Error: URL must include the key parameter (e.g., ws://host:port/?key=abcd1234)")
            sys.exit(1)
        client = ClipboardClient(args.url)
        try:
            asyncio.run(client.start())
        except SystemExit:
            pass
    else:
        server = ClipboardServer(port=args.port, key=args.key)
        asyncio.run(server.start())


if __name__ == "__main__":
    main()

