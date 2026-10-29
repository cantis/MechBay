from __future__ import annotations

import importlib.metadata
from pathlib import Path

import structlog
from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

from .config import Config, validate_runtime_config  # noqa: E402
from .extensions import init_db  # noqa: E402


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)

    # Load base config
    app.config.from_object(Config())

    # Apply any explicit overrides (used by tests to inject in-memory DB)
    if config_overrides:
        app.config.update(config_overrides)

    validate_runtime_config(app.config)

    # Only trust X-Forwarded-* headers when explicitly enabled for a
    # deployment behind a trusted reverse proxy that strips any client-
    # supplied forwarded headers and sets its own.
    app.config.setdefault("TRUST_PROXY_HEADERS", False)
    if app.config["TRUST_PROXY_HEADERS"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Configure structured logging
    from .logging import setup_logging

    setup_logging(
        debug=app.config.get("DEBUG", False),
        testing=app.config.get("TESTING", False),
    )
    logger = structlog.get_logger()

    # CSRF protection — always init so csrf_token() Jinja2 global is available,
    # but disable CSRF validation in test mode so test client POSTs work without tokens
    if app.config.get("TESTING"):
        app.config["WTF_CSRF_ENABLED"] = False

    from flask_wtf.csrf import CSRFProtect

    CSRFProtect(app)

    # Load version dynamically from package metadata
    try:
        version = importlib.metadata.version("mechbay")
    except importlib.metadata.PackageNotFoundError:
        version = "0.1.0"  # Fallback for development
    app.config["VERSION"] = version

    logger.info(
        "app_startup",
        version=version,
        debug=app.config.get("DEBUG", False),
        db_url=app.config.get("DATABASE_URL", ""),
    )

    # Ensure AppData MechBay directory exists (for Windows AppData-based DB)
    db_url = app.config.get("DATABASE_URL", "")
    if "AppData" in db_url or "mechbay.db" in db_url:
        # Extract path from sqlite:/// URL
        db_path = db_url.replace("sqlite:///", "")
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    # Initialize DB and create tables (uses possibly overridden DATABASE_URL)
    init_db(app)

    if not app.config.get("TESTING"):
        from .services.session_restore_service import restore_session

        restore_session()

    # Register blueprints
    from .blueprints.alpha_strike import bp as alpha_strike_bp
    from .blueprints.campaigns import bp as campaigns_bp
    from .blueprints.contracts import bp as contracts_bp
    from .blueprints.files import bp as files_bp
    from .blueprints.forces import bp as forces_bp
    from .blueprints.lance_templates import bp as lance_templates_bp
    from .blueprints.miniatures import bp as miniatures_bp

    app.register_blueprint(miniatures_bp)
    app.register_blueprint(forces_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(contracts_bp)
    app.register_blueprint(alpha_strike_bp)
    app.register_blueprint(lance_templates_bp)
    app.register_blueprint(files_bp)

    from .services import document_service

    @app.before_request
    def _flash_session_restore_messages():
        if app.config.get("_session_restore_messages_flashed"):
            return
        app.config["_session_restore_messages_flashed"] = True
        from .services.session_restore_service import consume_startup_messages

        for category, message in consume_startup_messages():
            flash(message, category)

    @app.context_processor
    def inject_document_status():
        try:
            return {"document_status": document_service.get_status()}
        except OSError:
            return {"document_status": {}}

    @app.context_processor
    def inject_active_campaign():
        from .services import campaign_service

        return {"active_campaign": campaign_service.get_active_campaign()}

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

    @app.errorhandler(400)
    def bad_request(error):
        logger.warning("http_400", path=request.path, description=str(error))
        if request.is_json:
            return jsonify({"success": False, "error": "Bad request"}), 400
        return render_template(
            "error.html",
            code=400,
            title="Bad Request",
            message="The server could not understand your request.",
            icon="fa-circle-exclamation",
            color="warning",
        ), 400

    @app.errorhandler(404)
    def not_found(error):
        logger.warning("http_404", path=request.path)
        if request.is_json:
            return jsonify({"success": False, "error": "Not found"}), 404
        return render_template(
            "error.html",
            code=404,
            title="Page Not Found",
            message="The page you're looking for doesn't exist or has been moved.",
            icon="fa-magnifying-glass",
            color="secondary",
        ), 404

    @app.errorhandler(500)
    def server_error(error):
        logger.error("http_500", path=request.path, exc_info=True)
        if request.is_json:
            return jsonify({"success": False, "error": "Internal server error"}), 500
        return render_template(
            "error.html",
            code=500,
            title="Server Error",
            message="Something went wrong. Please try again later.",
            icon="fa-triangle-exclamation",
            color="danger",
        ), 500

    return app
