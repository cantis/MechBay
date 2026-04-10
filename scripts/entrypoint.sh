#!/bin/bash
set -e

# Create data directory
mkdir -p /data

# Initialize database and seed data (single process to avoid race conditions)
echo "Initializing database..."
uv run python -c "
from app import create_app
app = create_app()
with app.app_context():
    print('Database initialized successfully')
"

# Start Gunicorn
echo "Starting Gunicorn..."
exec uv run gunicorn --bind 0.0.0.0:5000 --workers 4 server:app
