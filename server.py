"""Server entry point for Docker/Gunicorn deployment.

This module provides the WSGI application object for production deployments.
For desktop usage, use main.py instead, which includes the Waitress server and browser launch.
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    # This branch is only used for development testing with Flask's built-in server
    # In production, Gunicorn will import the 'app' object directly
    app.run(host="0.0.0.0", port=5000, debug=True)
