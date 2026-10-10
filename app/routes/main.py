from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..services import circulation, settings as settings_service
from ..services.errors import ValidationError
from . import get_store

bp = Blueprint("main", __name__)


@bp.route("/")
def dashboard():
    store = get_store()
    return render_template(
        "dashboard.html",
        stats=circulation.dashboard_stats(store),
        overdue=circulation.active_loans(store, overdue_only=True)[:6],
        recent=circulation.recent_activity(store),
    )


@bp.route("/settings", methods=["GET", "POST"])
def settings():
    store = get_store()
    if request.method == "POST":
        try:
            settings_service.update_settings(store, request.form)
        except ValidationError as exc:
            return render_template("settings.html", values=dict(request.form), errors=exc.errors), 400
        flash("Settings saved. The new fine rate applies to returns and overdue loans from now on.", "success")
        return redirect(url_for("main.settings"))
    return render_template("settings.html", values=settings_service.get_settings(store), errors={})
