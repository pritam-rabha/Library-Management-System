"""Authentication, CSRF protection, login throttling and security headers."""
import hmac
import secrets
import threading
import time
from urllib.parse import urlparse

from flask import abort, current_app, redirect, request, session, url_for

PUBLIC_ENDPOINTS = {"auth.login", "healthz", "static"}
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def csrf_token():
    """Return the session's CSRF token, creating it when needed."""
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def rotate_session(username):
    """Start a fresh session after login (prevents session fixation)."""
    session.clear()
    session.permanent = True
    session["admin"] = username
    session["_csrf"] = secrets.token_urlsafe(32)


def is_safe_next(target):
    if not target:
        return False
    parsed = urlparse(target)
    return not parsed.scheme and not parsed.netloc and target.startswith("/") and not target.startswith("//") \
        and "\\" not in target


class LoginThrottle:
    """Blocks an address after repeated failed logins for a short period."""

    def __init__(self):
        self._lock = threading.Lock()
        self._failures = {}

    def locked_for(self, key, limit, window):
        with self._lock:
            count, first = self._failures.get(key, (0, 0))
            if count and time.monotonic() - first > window:
                self._failures.pop(key, None)
                return 0
            if count >= limit:
                return int(window - (time.monotonic() - first)) + 1
            return 0

    def record_failure(self, key):
        with self._lock:
            count, first = self._failures.get(key, (0, time.monotonic()))
            self._failures[key] = (count + 1, first if count else time.monotonic())

    def reset(self, key):
        with self._lock:
            self._failures.pop(key, None)


def init_app(app):
    app.extensions["login_throttle"] = LoginThrottle()
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.before_request
    def guard():
        if request.method in UNSAFE_METHODS:
            sent = request.form.get("csrf_token") or request.headers.get("X-CSRFToken", "")
            expected = session.get("_csrf", "")
            if not expected or not hmac.compare_digest(str(sent), str(expected)):
                abort(400)
        if request.endpoint in PUBLIC_ENDPOINTS or request.endpoint is None:
            return None
        if not session.get("admin"):
            target = request.full_path.rstrip("?") if request.method == "GET" else None
            return redirect(url_for("auth.login", next=target) if target else url_for("auth.login"))
        return None

    @app.context_processor
    def inject_globals():
        return {"current_admin": session.get("admin"), "currency": current_app.config["CURRENCY_SYMBOL"]}

    @app.after_request
    def headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' https://cdn.jsdelivr.net; script-src 'self'; "
            "img-src 'self' data:; font-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'")
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        if current_app.config["APP_ENV"] == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
