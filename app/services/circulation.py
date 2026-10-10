"""Issuing, returning, fines and loan listings."""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from . import clock
from .errors import ConflictError, NotFoundError, ValidationError
from .validators import clean_text, normalize_id, parse_int


def overdue_days(due_date, as_of):
    """Whole days past the due date (0 if on time)."""
    return max(0, (as_of - clock.parse(due_date)).days)


def calculate_fine(days, fine_per_day):
    """Fine = overdue days x daily rate, rounded to two decimals."""
    amount = Decimal(str(fine_per_day)) * int(days)
    return float(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def issue_book(store, book_id, member_id, loan_days=None, today=None):
    today = today or clock.today()
    book_id, member_id = normalize_id(book_id), normalize_id(member_id)
    errors = {}
    with store.transaction() as data:
        settings = data["settings"]
        book = next((b for b in data["books"] if b["book_id"] == book_id), None)
        member = next((m for m in data["members"] if m["member_id"] == member_id), None)
        if book is None:
            errors["book_id"] = "Select a valid book."
        if member is None:
            errors["member_id"] = "Select a registered member."
        days = settings["loan_days"]
        if clean_text(loan_days):
            days = parse_int(loan_days, 1, 365)
            if days is None:
                errors["loan_days"] = "Loan period must be a whole number of days from 1 to 365."
        if errors:
            raise ValidationError(errors)

        if book["available_copies"] < 1:
            raise ConflictError("'%s' has no copies available to issue." % book["title"])
        active = [t for t in data["transactions"] if t["member_id"] == member_id and t["return_date"] is None]
        if any(t["book_id"] == book_id for t in active):
            raise ConflictError("%s already has a copy of this book on loan." % member["name"])
        if len(active) >= settings["max_loans_per_member"]:
            raise ConflictError("%s has reached the limit of %d books on loan." % (
                member["name"], settings["max_loans_per_member"]))

        txn = {
            "txn_id": "T%05d" % (1 + max([int(t["txn_id"][1:]) for t in data["transactions"]] or [0])),
            "book_id": book_id, "book_title": book["title"],
            "member_id": member_id, "member_name": member["name"],
            "issue_date": today.isoformat(),
            "due_date": (today + timedelta(days=days)).isoformat(),
            "return_date": None, "overdue_days": 0, "fine": 0.0, "fine_per_day": None,
        }
        book["available_copies"] -= 1
        data["transactions"].append(txn)
    return txn


def return_book(store, txn_id, today=None):
    today = today or clock.today()
    with store.transaction() as data:
        txn = next((t for t in data["transactions"] if t["txn_id"] == txn_id), None)
        if txn is None:
            raise NotFoundError("Transaction %s was not found." % txn_id)
        if txn["return_date"] is not None:
            raise ConflictError("This book was already returned on %s." % txn["return_date"])
        rate = data["settings"]["fine_per_day"]
        days = overdue_days(txn["due_date"], today)
        txn.update(return_date=today.isoformat(), overdue_days=days,
                   fine=calculate_fine(days, rate), fine_per_day=rate)
        book = next((b for b in data["books"] if b["book_id"] == txn["book_id"]), None)
        if book is not None:
            book["available_copies"] = min(book["total_copies"], book["available_copies"] + 1)
        return dict(txn)


def _enrich(txn, rate, today):
    row = dict(txn)
    if txn["return_date"] is None:
        days = overdue_days(txn["due_date"], today)
        row.update(overdue_days=days, is_overdue=days > 0, fine=calculate_fine(days, rate),
                   days_left=(clock.parse(txn["due_date"]) - today).days)
    else:
        row.update(is_overdue=False, days_left=None)
    return row


def active_loans(store, overdue_only=False, query="", today=None):
    today = today or clock.today()
    data = store.read()
    rate = data["settings"]["fine_per_day"]
    rows = [_enrich(t, rate, today) for t in data["transactions"] if t["return_date"] is None]
    if overdue_only:
        rows = [r for r in rows if r["is_overdue"]]
    text = clean_text(query).lower()
    if text:
        rows = [r for r in rows if text in " ".join(
            (r["book_title"], r["book_id"], r["member_name"], r["member_id"])).lower()]
    return sorted(rows, key=lambda r: (r["due_date"], r["txn_id"]))


def history(store, status="all", query="", today=None):
    today = today or clock.today()
    data = store.read()
    rate = data["settings"]["fine_per_day"]
    rows = [_enrich(t, rate, today) for t in data["transactions"]]
    if status == "issued":
        rows = [r for r in rows if r["return_date"] is None]
    elif status == "returned":
        rows = [r for r in rows if r["return_date"] is not None]
    text = clean_text(query).lower()
    if text:
        rows = [r for r in rows if text in " ".join(
            (r["book_title"], r["book_id"], r["member_name"], r["member_id"])).lower()]
    return sorted(rows, key=lambda r: r["txn_id"], reverse=True)


def available_books(store, query=""):
    from .books import matches_query
    books = [b for b in store.read()["books"] if b["available_copies"] > 0]
    if query:
        books = [b for b in books if matches_query(b, query)]
    return sorted(books, key=lambda b: b["title"].lower())


def dashboard_stats(store, today=None):
    today = today or clock.today()
    data = store.read()
    active = [t for t in data["transactions"] if t["return_date"] is None]
    return {
        "total_books": len(data["books"]),
        "total_copies": sum(b["total_copies"] for b in data["books"]),
        "available_copies": sum(b["available_copies"] for b in data["books"]),
        "issued_books": len(active),
        "members": len(data["members"]),
        "overdue_books": sum(1 for t in active if overdue_days(t["due_date"], today) > 0),
    }


def recent_activity(store, limit=6):
    rows = sorted(store.read()["transactions"], key=lambda t: t["txn_id"], reverse=True)
    return rows[:limit]
