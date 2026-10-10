from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from ..security import is_safe_next
from ..services import books as book_service, circulation as service, members as member_service, settings as settings_service
from ..services.errors import ConflictError, ValidationError
from . import get_store

bp = Blueprint("circulation", __name__, url_prefix="/circulation")


def _issue_context(store, values, errors):
    return dict(books=service.available_books(store), members=member_service.list_members(store),
                settings=settings_service.get_settings(store), values=values, errors=errors)


@bp.route("/issue", methods=["GET", "POST"])
def issue():
    store = get_store()
    if request.method == "POST":
        try:
            txn = service.issue_book(store, request.form.get("book_id"), request.form.get("member_id"),
                                     request.form.get("loan_days"))
        except ValidationError as exc:
            return render_template("circulation/issue.html", **_issue_context(store, dict(request.form), exc.errors)), 400
        except ConflictError as exc:
            flash(str(exc), "danger")
            return render_template("circulation/issue.html", **_issue_context(store, dict(request.form), {})), 409
        flash("Issued '%s' to %s. Due on %s." % (txn["book_title"], txn["member_name"],
                                                 _pretty(txn["due_date"])), "success")
        return redirect(url_for("circulation.issued"))
    return render_template("circulation/issue.html",
                           **_issue_context(store, {"book_id": request.args.get("book_id", ""),
                                                    "member_id": request.args.get("member_id", "")}, {}))


def _pretty(iso):
    from datetime import date
    return date.fromisoformat(iso).strftime("%d %b %Y")


@bp.route("/available")
def available():
    q = request.args.get("q", "")
    return render_template("circulation/available.html", books=service.available_books(get_store(), q), q=q)


@bp.route("/issued")
def issued():
    q = request.args.get("q", "")
    status = request.args.get("status", "all")
    rows = service.active_loans(get_store(), overdue_only=(status == "overdue"), query=q)
    return render_template("circulation/issued.html", loans=rows, q=q, status=status)


@bp.route("/return/<txn_id>", methods=["POST"])
def return_book(txn_id):
    next_url = request.form.get("next", "")
    try:
        txn = service.return_book(get_store(), txn_id)
        if txn["fine"] > 0:
            flash("Returned '%s' from %s. Overdue days: %d. Fine due: %s%.2f (at %s%.2f per day)." % (
                txn["book_title"], txn["member_name"], txn["overdue_days"], current_app.config["CURRENCY_SYMBOL"],
                txn["fine"], current_app.config["CURRENCY_SYMBOL"], txn["fine_per_day"]), "warning")
        else:
            flash("Returned '%s' from %s on time. No fine." % (txn["book_title"], txn["member_name"]), "success")
    except ConflictError as exc:
        flash(str(exc), "danger")
    return redirect(next_url if is_safe_next(next_url) else url_for("circulation.issued"))


@bp.route("/history")
def history():
    q = request.args.get("q", "")
    status = request.args.get("status", "all")
    return render_template("circulation/history.html", rows=service.history(get_store(), status, q), q=q, status=status)
