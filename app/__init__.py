from __future__ import annotations

from pathlib import Path

from flask import Flask, redirect, url_for

from .config import Config
from .extensions import init_db


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)

    # Load base config
    app.config.from_object(Config())

    # Apply any explicit overrides (used by tests to inject in-memory DB)
    if config_overrides:
        app.config.update(config_overrides)

    # Ensure instance/data directory exists (only relevant for file-based DBs)
    data_dir = Path(__file__).resolve().parent
    (data_dir).mkdir(parents=True, exist_ok=True)

    # Initialize DB and create tables (uses possibly overridden DATABASE_URL)
    init_db(app)

    # Register blueprints
    from .blueprints.forces import bp as forces_bp
    from .blueprints.lance_templates import bp as lance_templates_bp
    from .blueprints.miniatures import bp as miniatures_bp

    app.register_blueprint(miniatures_bp)
    app.register_blueprint(forces_bp)
    app.register_blueprint(lance_templates_bp)

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
