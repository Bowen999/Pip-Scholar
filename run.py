"""启动 Pip-Scholar 本地 Web 应用：python run.py [--port 8000] [--no-browser]"""

import argparse
import threading
import webbrowser

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Pip-Scholar local web app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    args = parser.parse_args()

    url = f"http://127.0.0.1:{args.port}" if args.host in ("127.0.0.1", "0.0.0.0") else f"http://{args.host}:{args.port}"
    print(f"Pip-Scholar → {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        threading.Timer(1.5, webbrowser.open, [url]).start()
    uvicorn.run("backend.main:app", host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
