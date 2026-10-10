"""Feature 2: automatic, configurable fines for late returns."""
from datetime import timedelta

import pytest

from app.services import circulation, clock, settings
from app.services.errors import ValidationError


def _issue_overdue(store, days_overdue, book_id="B001", member_id="M001"):
    """Issue a loan whose due date was `days_overdue` days ago."""
    issued = clock.today() - timedelta(days=14 + days_overdue)
    return circulation.issue_book(store, book_id, member_id, today=issued)


@pytest.mark.parametrize("days,rate,expected", [
    (0, 2, 0.0), (1, 2, 2.0), (5, 2, 10.0), (30, 2, 60.0), (3, 0.75, 2.25), (7, 1.5, 10.5), (4, 0, 0.0),
])
def test_fine_formula(days, rate, expected):
    assert circulation.calculate_fine(days, rate) == expected


def test_overdue_days_counts_whole_days_after_due_date():
    assert circulation.overdue_days("2026-03-10", clock.parse("2026-03-10")) == 0
    assert circulation.overdue_days("2026-03-10", clock.parse("2026-03-09")) == 0
    assert circulation.overdue_days("2026-03-10", clock.parse("2026-03-11")) == 1
    assert circulation.overdue_days("2026-03-10", clock.parse("2026-04-09")) == 30


def test_late_return_stores_overdue_days_and_fine(library):
    txn = _issue_overdue(library, 6)
    returned = circulation.return_book(library, txn["txn_id"])
    assert returned["overdue_days"] == 6
    assert returned["fine"] == 12.0
    assert returned["fine_per_day"] == 2.0
    stored = library.read()["transactions"][0]
    assert stored["fine"] == 12.0


def test_on_time_return_has_no_fine(library):
    txn = circulation.issue_book(library, "B001", "M001", today=clock.today() - timedelta(days=14))
    assert circulation.return_book(library, txn["txn_id"])["fine"] == 0


def test_fine_rate_is_configurable(library):
    settings.update_settings(library, {"fine_per_day": "5.50", "loan_days": "14", "max_loans_per_member": "3"})
    txn = _issue_overdue(library, 4)
    assert circulation.return_book(library, txn["txn_id"])["fine"] == 22.0


def test_changing_the_rate_does_not_alter_fines_already_recorded(library):
    txn = _issue_overdue(library, 3)
    circulation.return_book(library, txn["txn_id"])
    settings.update_settings(library, {"fine_per_day": "10", "loan_days": "14", "max_loans_per_member": "3"})
    assert library.read()["transactions"][0]["fine"] == 6.0


@pytest.mark.parametrize("field,value", [
    ("fine_per_day", "-1"), ("fine_per_day", "abc"), ("fine_per_day", ""), ("fine_per_day", "1.234"),
    ("fine_per_day", "99999"), ("loan_days", "0"), ("loan_days", "x"), ("max_loans_per_member", "0"),
])
def test_invalid_settings_are_rejected(library, field, value):
    form = {"fine_per_day": "2", "loan_days": "14", "max_loans_per_member": "3", field: value}
    with pytest.raises(ValidationError) as caught:
        settings.update_settings(library, form)
    assert field in caught.value.errors
    assert settings.get_settings(library)["fine_per_day"] == 2.0


def test_settings_page_saves_new_rate(admin, post, library):
    response = post(admin, "/settings", {"fine_per_day": "3.25", "loan_days": "10", "max_loans_per_member": "4"})
    assert response.status_code == 302
    assert settings.get_settings(library) == {"fine_per_day": 3.25, "loan_days": 10, "max_loans_per_member": 4}
    bad = post(admin, "/settings", {"fine_per_day": "-5", "loan_days": "10", "max_loans_per_member": "4"})
    assert bad.status_code == 400


def test_issued_page_shows_overdue_days_and_running_fine(admin, library):
    _issue_overdue(library, 6)
    page = admin.get("/circulation/issued").get_data(as_text=True)
    assert "Overdue 6 days" in page
    assert "Rs.12.00" in page


def test_return_message_shows_overdue_days_and_total_fine(admin, post, library):
    txn = _issue_overdue(library, 6)
    response = post(admin, "/circulation/return/" + txn["txn_id"], follow_redirects=True)
    text = response.get_data(as_text=True)
    assert "Overdue days: 6" in text and "Rs.12.00" in text
    history = admin.get("/circulation/history").get_data(as_text=True)
    assert "Rs.12.00" in history


def test_active_loan_accrued_fine_is_calculated(library):
    _issue_overdue(library, 10)
    loan = circulation.active_loans(library)[0]
    assert loan["is_overdue"] and loan["overdue_days"] == 10 and loan["fine"] == 20.0
