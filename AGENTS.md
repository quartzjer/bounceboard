# Bounceboard Agent Guide

This document provides an overview of the repository and how it is organized. It also offers a quick reference for contributors.

## Repository Layout

- `bounceboard/app.py` – command line entry point and runtime options.
- `bounceboard/service.py` – `ClipboardServer` and `ClipboardClient` network implementation.
- `bounceboard/sync.py` – `ClipboardConnection` helper for WebSocket framing.
- `bounceboard/clipboard/` – clipboard backends and utilities:
  - `common.py` – helpers shared by the backends.
  - `backends.py` – selects and wraps platform backends.
  - `manager.py` – `ClipboardManager` for async clipboard polling/caching.
  - `linux.py`, `macos.py`, `win.py` – implementations for each operating system.
- `bounceboard/static/index.html` – minimal browser UI served when running in server mode.
- `tests/` – unit tests for clipboard code and manager.
- `pyproject.toml` – project configuration and dependencies. The entry point is defined as the `bb` console script.
- `requirements.txt` – dependency list for development environments.
- `README.md` – usage instructions and general project description.

## Usage Notes

Run the tool via the `bb` command defined in `pyproject.toml`. The application can operate in either **server** or **client** mode. The network layer uses TLS with the self-signed `cert.pem` and `key.pem` provided for local development.

## Testing

Run unit tests with:

```
python -m unittest discover -s tests -v
```

Currently no dedicated linting configuration is provided.
