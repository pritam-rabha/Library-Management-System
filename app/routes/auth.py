import hmac

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from .. import security

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin"):
        return redirect(url_for("main.dashboard"))
    cfg = current_app.config
    next_url = request.values.get("next", "")
    if request.method == "POST":
        throttle = current_app.extensions["login_throttle"]
        key = request.remote_addr or "unknown"
        wait = throttle.locked_for(key, cfg["LOGIN_MAX_ATTEMPTS"], cfg["LOGIN_LOCK_SECONDS"])
        if wait:
            flash("Too many failed attempts. Try again in %d seconds." % wait, "danger")
            return render_template("login.html", next_url=next_url), 429
        if not cfg["ADMIN_USERNAME"] or not cfg["ADMIN_PASSWORD_HASH"]:
            flash("Administrator credentials are not configured on the server. See the README.", "danger")
            return render_template("login.html", next_url=next_url), 503
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user_ok = hmac.compare_digest(username.encode(), cfg["ADMIN_USERNAME"].encode())
        try:
            pass_ok = check_password_hash(cfg["ADMIN_PASSWORD_HASH"], password)
        except ValueError:
            pass_ok = False
        if user_ok and pass_ok:
            throttle.reset(key)
            security.rotate_session(cfg["ADMIN_USERNAME"])
            return redirect(next_url if security.is_safe_next(next_url) else url_for("main.dashboard"))
        throttle.record_failure(key)
        flash("Incorrect username or password.", "danger")
        return render_template("login.html", next_url=next_url), 401
    return render_template("login.html", next_url=next_url)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
