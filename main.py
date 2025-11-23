import os
import threading
import time
import webbrowser

from waitress import serve

from app import create_app


def main():
    app = create_app()

    # Get version and debug settings
    version = app.config.get("VERSION", "0.1.0")
    debug_mode = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")
    app.debug = debug_mode

    # Server configuration
    host = "127.0.0.1"
    port = 5001
    url = f"http://{host}:{port}"

    print(f"MechBay v{version}")
    print(f"Starting server at {url}")
    print("Press Ctrl+C to stop the server")
    print("-" * 50)

    # Start Waitress in background thread
    server_thread = threading.Thread(target=lambda: serve(app, host=host, port=port), daemon=True)
    server_thread.start()

    # Wait briefly for server to start, then open browser
    time.sleep(1)
    print(f"Opening browser at {url}")
    webbrowser.open(url)

    # Keep main thread alive
    try:
        server_thread.join()
    except KeyboardInterrupt:
        print("\nShutting down MechBay...")


if __name__ == "__main__":
    main()
