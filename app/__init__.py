from __future__ import annotations

import importlib.metadata
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, url_for

load_dotenv()

from .config import Config  # noqa: E402
from .extensions import init_db  # noqa: E402


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)

    # Load base config
    app.config.from_object(Config())

    # Apply any explicit overrides (used by tests to inject in-memory DB)
    if config_overrides:
        app.config.update(config_overrides)

    # Load version dynamically from package metadata
    try:
        version = importlib.metadata.version("mechbay")
    except importlib.metadata.PackageNotFoundError:
        version = "0.1.0"  # Fallback for development
    app.config["VERSION"] = version

    # Ensure AppData MechBay directory exists (for Windows AppData-based DB)
    db_url = app.config.get("DATABASE_URL", "")
    if "AppData" in db_url or "mechbay.db" in db_url:
        # Extract path from sqlite:/// URL
        db_path = db_url.replace("sqlite:///", "")
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    # Initialize DB and create tables (uses possibly overridden DATABASE_URL)
    init_db(app)

    # Auto-seed database on first run (skip for test environments)
    if not app.config.get("TESTING"):
        from .services.miniature_service import get_all_miniatures

        miniatures = get_all_miniatures()
        if len(miniatures) == 0:
            from .seed import run

            count = run()
            print(f"Demo data loaded: {count} records created")

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

    @app.route("/health")
    def health():
        """Health check endpoint for monitoring."""
        return jsonify({"status": "ok", "version": app.config["VERSION"]})

    @app.route("/about")
    def about():
        """About page with version information."""
        return render_template("about.html", version=app.config["VERSION"])

    return app
