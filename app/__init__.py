"""Library Management System - application factory."""
import logging
import secrets

from flask import Flask, redirect, render_template, request, session, url_for, flash
from werkzeug.middleware.proxy_fix import ProxyFix

from . import security
from .config import build_config, load_dotenv
from .services import clock, seed
from .services.errors import NotFoundError, StorageError
from .storage import JsonStore

log = logging.getLogger(__name__)


def create_app(test_config=None):
    """Create and configure the Flask application."""
    if test_config is None:
        load_dotenv()

    app = Flask(__name__)
    app.config.update(build_config())
    if test_config:
        app.config.update(test_config)

    _ensure_secret_key(app)
    clock.configure(app.config["TIMEZONE"])

    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    store = JsonStore(
        app.config["DATA_FILE"],
        default_factory=lambda: seed.initial_dataset(app.config),
    )
    app.extensions["store"] = store
    try:
        store.read()  # creates the runtime file on first start
    except StorageError as exc:
        log.error("Storage problem at start-up: %s", exc)

    security.init_app(app)
    _register_blueprints(app)
    _register_filters(app)
    _register_error_handlers(app)
    return app


def _ensure_secret_key(app):
    key = app.config.get("SECRET_KEY")
    if key and len(key) >= 16:
        return
    if app.config["APP_ENV"] == "production":
        raise RuntimeError("SECRET_KEY must be set (16+ characters) when APP_ENV=production.")
    log.warning("SECRET_KEY not set; using a temporary random key (sessions reset on restart).")
    app.config["SECRET_KEY"] = secrets.token_hex(32)


def _register_blueprints(app):
    from .routes import auth, backup, books, circulation, main, members

    for module in (auth, main, books, members, circulation, backup):
        app.register_blueprint(module.bp)


def _register_filters(app):
    from datetime import date

    def fmt_date(value):
        if not value:
            return "-"
        try:
            return date.fromisoformat(value).strftime("%d %b %Y")
        except (TypeError, ValueError):
            return str(value)

    def money(value):
        try:
            return "{}{:,.2f}".format(app.config["CURRENCY_SYMBOL"], float(value or 0))
        except (TypeError, ValueError):
            return str(value)

    app.jinja_env.filters["fmt_date"] = fmt_date
    app.jinja_env.filters["money"] = money
    app.jinja_env.globals["zip"] = zip


def _register_error_handlers(app):
    def render_error(code, title, message):
        return render_template("error.html", code=code, title=title, message=message), code

    @app.errorhandler(400)
    def bad_request(_e):
        return render_error(400, "Request could not be processed",
                            "The form was invalid or has expired. Go back, reload the page and try again.")

    @app.errorhandler(404)
    def not_found(_e):
        return render_error(404, "Page not found", "The page you requested does not exist.")

    @app.errorhandler(NotFoundError)
    def record_not_found(e):
        return render_error(404, "Record not found", str(e))

    @app.errorhandler(405)
    def not_allowed(_e):
        return render_error(405, "Method not allowed", "This action is not available for that address.")

    @app.errorhandler(413)
    def too_large(_e):
        flash("The uploaded file is too large. The limit is 2 MB.", "danger")
        return redirect(url_for("backup.index"))

    @app.errorhandler(StorageError)
    def storage_failure(e):
        log.error("Storage failure: %s", e)
        return render_error(503, "Data storage problem", str(e))

    @app.errorhandler(500)
    def server_error(_e):
        return render_error(500, "Unexpected error", "Something went wrong. The details were written to the server log.")
