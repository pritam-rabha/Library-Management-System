"""Initial data for a brand-new runtime file.

The sample file under data/sample/ is only ever read; the application writes to the
runtime file (data/runtime/library.json by default).
"""
import json
import logging
from datetime import timedelta
from pathlib import Path

from . import clock
from .circulation import calculate_fine

log = logging.getLogger(__name__)


def default_settings(config):
    try:
        fine = float(config["FINE_PER_DAY"])
    except (TypeError, ValueError):
        fine = 2.0
    return {"fine_per_day": fine, "loan_days": int(config["LOAN_DAYS"]),
            "max_loans_per_member": int(config["MAX_LOANS_PER_MEMBER"])}


def empty_dataset(config):
    return {"settings": default_settings(config), "books": [], "members": [], "transactions": []}


def build_from_sample(sample, config, today=None):
    """Turn the sample file (with loans relative to today) into a full dataset."""
    today = today or clock.today()
    data = empty_dataset(config)
    data["members"] = [dict(m, joined_date=(today - timedelta(days=400)).isoformat()) for m in sample["members"]]
    books = {b["book_id"]: dict(b, available_copies=b["total_copies"]) for b in sample["books"]}
    members = {m["member_id"]: m for m in data["members"]}
    settings = data["settings"]
    loans = sorted(sample.get("loans", []), key=lambda l: -l["issued_days_ago"])
    for number, loan in enumerate(loans, start=1):
        book, member = books[loan["book_id"]], members[loan["member_id"]]
        issued = today - timedelta(days=loan["issued_days_ago"])
        due = issued + timedelta(days=settings["loan_days"])
        txn = {"txn_id": "T%05d" % number, "book_id": book["book_id"], "book_title": book["title"],
               "member_id": member["member_id"], "member_name": member["name"],
               "issue_date": issued.isoformat(), "due_date": due.isoformat(),
               "return_date": None, "overdue_days": 0, "fine": 0.0, "fine_per_day": None}
        returned_ago = loan.get("returned_days_ago")
        if returned_ago is None:
            book["available_copies"] -= 1
        else:
            returned = today - timedelta(days=returned_ago)
            days = max(0, (returned - due).days)
            txn.update(return_date=returned.isoformat(), overdue_days=days,
                       fine=calculate_fine(days, settings["fine_per_day"]),
                       fine_per_day=settings["fine_per_day"])
        data["transactions"].append(txn)
    data["books"] = list(books.values())
    return data


def initial_dataset(config):
    if config.get("SEED_SAMPLE_DATA") and Path(config["SAMPLE_FILE"]).is_file():
        try:
            sample = json.loads(Path(config["SAMPLE_FILE"]).read_text(encoding="utf-8"))
            return build_from_sample(sample, config)
        except (OSError, ValueError, KeyError) as exc:
            log.error("Sample data could not be used (%s); starting with an empty library.", exc)
    return empty_dataset(config)
