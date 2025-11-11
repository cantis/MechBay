from __future__ import annotations

from pathlib import Path

from flask import Flask, redirect, url_for

from .config import Config
from .extensions import init_db


def create_app() -> Flask:
    app = Flask(__name__)

    # Load base config
    app.config.from_object(Config())

    # Ensure instance/data directory exists
    data_dir = Path(__file__).resolve().parent
    (data_dir).mkdir(parents=True, exist_ok=True)

    # Initialize DB and create tables
    init_db(app)

    # Register blueprints
    from .blueprints.miniatures import bp as miniatures_bp

    app.register_blueprint(miniatures_bp)

    @app.route("/")
    def index():
        return redirect(url_for("miniatures.list_miniatures"))

    @app.route("/about")
    def about():
        return (
            "<div style='padding:2rem;font-family:system-ui'>"
            "<h1>MechBay</h1>"
            "<p>A simple BattleTech miniature inventory built with Flask.</p>"
            "</div>"
        )

    return app
