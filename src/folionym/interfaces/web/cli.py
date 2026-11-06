"""Command-line launcher for the loopback Folionym browser application."""

from __future__ import annotations

import argparse
import secrets
import socket
import sys
import threading
import webbrowser


def main(argv: list[str] | None = None) -> None:
    """Launch the packaged local browser frontend."""
    parser = argparse.ArgumentParser(description="Launch Folionym's local browser frontend.")
    parser.add_argument("--port", type=int, default=8765, help="loopback port (default: 8765)")
    parser.add_argument("--no-open", action="store_true", help="do not open the default browser")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit("Install the browser frontend with: pip install 'folionym[web]'") from exc

    from .app import create_app, default_static_dir

    static_dir = default_static_dir()
    if not (static_dir / "index.html").is_file():
        raise SystemExit("Packaged browser assets are missing. Reinstall Folionym with the web extra.")

    host = "127.0.0.1"
    # Bind before printing or opening the link, so it can only reach this process.
    try:
        listener = socket.create_server((host, args.port))
    except OSError as exc:
        raise SystemExit(f"Port {args.port} is not available ({exc.strerror}). Choose another with --port.") from exc
    token = secrets.token_urlsafe(32)
    url = f"http://{host}:{args.port}/source?token={token}"
    print(f"Folionym is running at {url}", file=sys.stderr, flush=True)
    if not args.no_open:
        # A thread, because console browsers block until they exit; the socket already listens.
        threading.Thread(target=webbrowser.open, args=(url,), name="folionym-browser-open", daemon=True).start()
    app = create_app(static_dir=static_dir, launch_token=token)
    uvicorn.Server(uvicorn.Config(app, log_level="warning")).run(sockets=[listener])


if __name__ == "__main__":
    main()
