"""Feature 1: issue and return books."""
from datetime import timedelta

import pytest

from app.services import books, circulation, clock
from app.services.errors import ConflictError, NotFoundError, ValidationError


def test_issue_records_dates_and_reduces_available_copies(library):
    today = clock.today()
    txn = circulation.issue_book(library, "B001", "M001", today=today)
    assert txn["issue_date"] == today.isoformat()
    assert txn["due_date"] == (today + timedelta(days=14)).isoformat()
    assert txn["return_date"] is None
    assert books.get_book(library, "B001")["available_copies"] == 1


def test_custom_loan_period(library):
    today = clock.today()
    txn = circulation.issue_book(library, "B001", "M001", loan_days="7", today=today)
    assert txn["due_date"] == (today + timedelta(days=7)).isoformat()


@pytest.mark.parametrize("days", ["0", "-2", "abc", "366", "1.5"])
def test_invalid_loan_period_is_rejected(library, days):
    with pytest.raises(ValidationError) as caught:
        circulation.issue_book(library, "B001", "M001", loan_days=days)
    assert "loan_days" in caught.value.errors
    assert books.get_book(library, "B001")["available_copies"] == 2


def test_cannot_issue_when_no_copy_is_available(library):
    circulation.issue_book(library, "B002", "M001")  # B002 has a single copy
    with pytest.raises(ConflictError) as caught:
        circulation.issue_book(library, "B002", "M002")
    assert "no copies available" in str(caught.value)
    assert books.get_book(library, "B002")["available_copies"] == 0
    assert len(library.read()["transactions"]) == 1


def test_unknown_book_or_member_is_rejected(library):
    with pytest.raises(ValidationError) as caught:
        circulation.issue_book(library, "NOPE", "M001")
    assert "book_id" in caught.value.errors
    with pytest.raises(ValidationError) as caught:
        circulation.issue_book(library, "B001", "GHOST")
    assert "member_id" in caught.value.errors
    assert library.read()["transactions"] == []


def test_member_cannot_borrow_the_same_title_twice(library):
    circulation.issue_book(library, "B001", "M001")
    with pytest.raises(ConflictError):
        circulation.issue_book(library, "B001", "M001")


def test_loan_limit_per_member(library):
    for book_id in ("B001", "B002", "B003"):
        circulation.issue_book(library, book_id, "M001")
    books.add_book(library, {"book_id": "B004", "title": "Extra", "author": "Someone", "total_copies": "1"})
    with pytest.raises(ConflictError) as caught:
        circulation.issue_book(library, "B004", "M001")
    assert "limit" in str(caught.value)


def test_return_records_date_and_restores_copy(library):
    txn = circulation.issue_book(library, "B001", "M001")
    returned = circulation.return_book(library, txn["txn_id"])
    assert returned["return_date"] == clock.today().isoformat()
    assert returned["fine"] == 0 and returned["overdue_days"] == 0
    assert books.get_book(library, "B001")["available_copies"] == 2


def test_returned_copy_can_be_issued_again(library):
    txn = circulation.issue_book(library, "B002", "M001")
    circulation.return_book(library, txn["txn_id"])
    circulation.issue_book(library, "B002", "M002")
    assert books.get_book(library, "B002")["available_copies"] == 0


def test_cannot_return_twice_or_return_unknown(library):
    txn = circulation.issue_book(library, "B001", "M001")
    circulation.return_book(library, txn["txn_id"])
    with pytest.raises(ConflictError):
        circulation.return_book(library, txn["txn_id"])
    assert books.get_book(library, "B001")["available_copies"] == 2
    with pytest.raises(NotFoundError):
        circulation.return_book(library, "T99999")


def test_transaction_ids_are_unique_and_sequential(library):
    first = circulation.issue_book(library, "B001", "M001")
    second = circulation.issue_book(library, "B003", "M001")
    assert (first["txn_id"], second["txn_id"]) == ("T00001", "T00002")


def test_issue_and_return_through_the_web(admin, post, library):
    response = post(admin, "/circulation/issue", {"book_id": "B001", "member_id": "M001", "loan_days": ""})
    assert response.status_code == 302
    page = admin.get("/circulation/issued").get_data(as_text=True)
    assert "Python Basics" in page and "Asha Rao" in page
    txn_id = library.read()["transactions"][0]["txn_id"]
    done = post(admin, "/circulation/return/" + txn_id, {"next": "/circulation/issued"}, follow_redirects=True)
    assert "on time" in done.get_data(as_text=True)
    assert books.get_book(library, "B001")["available_copies"] == 2


def test_web_refuses_to_issue_an_unavailable_book(admin, post, library):
    post(admin, "/circulation/issue", {"book_id": "B002", "member_id": "M001"})
    response = post(admin, "/circulation/issue", {"book_id": "B002", "member_id": "M002"})
    assert response.status_code == 409
    assert "no copies available" in response.get_data(as_text=True)


def test_web_issue_validation_errors(admin, post, library):
    response = post(admin, "/circulation/issue", {"book_id": "", "member_id": ""})
    assert response.status_code == 400
    assert "Select a valid book." in response.get_data(as_text=True)
