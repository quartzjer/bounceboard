# Bounceboard Agent Guide

This document provides an overview of the repository and how it is organized. It also offers a quick reference for contributors.

## Repository Layout

- `bounceboard/app.py` – main application module. Contains the command line interface and the logic for running in server or client mode.
- `bounceboard/clipboard/` – per-platform clipboard backends and common utilities:
  - `common.py` – helpers shared by the backends.
  - `linux.py`, `macos.py`, `win.py` – implementations for each operating system.
- `bounceboard/static/index.html` – minimal browser UI served when running in server mode.
- `pyproject.toml` – project configuration and dependencies. The entry point is defined as the `bb` console script.
- `requirements.txt` – dependency list for development environments.
- `README.md` – usage instructions and general project description.

## Usage Notes

Run the tool via the `bb` command defined in `pyproject.toml`. The application can operate in either **server** or **client** mode as described in the README. The server expects TLS certificates (`cert.pem` and `key.pem`) which are already included for local development.

## Testing

The repository currently does not contain automated tests or linting configuration.
