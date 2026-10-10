"""Feature 5: available books, issued books, overdue highlighting and dashboard figures."""
from datetime import timedelta

from app.services import circulation, clock


def test_available_books_page_lists_copy_counts(admin, library):
    circulation.issue_book(library, "B001", "M001")
    page = admin.get("/circulation/available").get_data(as_text=True)
    assert "Python Basics" in page and "Algorithms Unlocked" in page
    row = [r for r in page.split("<tr>") if "Python Basics" in r][0]
    assert '<td class="text-end">1</td><td class="text-end">2</td>' in row  # 1 available of 2 total


def test_available_books_excludes_books_with_no_copies(admin, library):
    circulation.issue_book(library, "B002", "M001")
    page = admin.get("/circulation/available").get_data(as_text=True)
    assert "Data Structures" not in page


def test_issued_page_shows_borrower_and_due_date(admin, library):
    today = clock.today()
    circulation.issue_book(library, "B001", "M002", today=today)
    page = admin.get("/circulation/issued").get_data(as_text=True)
    assert "Ben Das" in page and "M002" in page
    assert (today + timedelta(days=14)).strftime("%d %b %Y") in page
    assert "row-overdue" not in page


def test_overdue_loans_are_highlighted_and_on_time_loans_are_not(admin, library):
    circulation.issue_book(library, "B001", "M001", today=clock.today() - timedelta(days=30))
    circulation.issue_book(library, "B003", "M002")
    page = admin.get("/circulation/issued").get_data(as_text=True)
    assert page.count('class="row-overdue"') == 1
    late_row = [r for r in page.split("<tr") if "Asha Rao" in r][0]
    assert "row-overdue" in late_row and "Overdue 16 days" in late_row
    ok_row = [r for r in page.split("<tr") if "Ben Das" in r][0]
    assert "row-overdue" not in ok_row


def test_overdue_filter_shows_only_overdue(admin, library):
    circulation.issue_book(library, "B001", "M001", today=clock.today() - timedelta(days=30))
    circulation.issue_book(library, "B003", "M002")
    page = admin.get("/circulation/issued?status=overdue").get_data(as_text=True)
    assert "Asha Rao" in page and "Ben Das" not in page


def test_loan_due_today_is_not_overdue(library):
    circulation.issue_book(library, "B001", "M001", today=clock.today() - timedelta(days=14))
    loan = circulation.active_loans(library)[0]
    assert loan["overdue_days"] == 0 and not loan["is_overdue"]


def test_dashboard_statistics(admin, library):
    circulation.issue_book(library, "B001", "M001", today=clock.today() - timedelta(days=20))
    circulation.issue_book(library, "B003", "M002")
    stats = circulation.dashboard_stats(library)
    assert stats == {"total_books": 3, "total_copies": 6, "available_copies": 4, "issued_books": 2,
                     "members": 3, "overdue_books": 1}
    page = admin.get("/").get_data(as_text=True)
    for label in ("Total books", "Available copies", "Issued books", "Registered users", "Overdue books"):
        assert label in page


def test_history_page_and_status_filter(admin, library):
    txn = circulation.issue_book(library, "B001", "M001")
    circulation.return_book(library, txn["txn_id"])
    circulation.issue_book(library, "B003", "M002")
    assert "Asha Rao" in admin.get("/circulation/history?status=returned").get_data(as_text=True)
    assert "Ben Das" not in admin.get("/circulation/history?status=returned").get_data(as_text=True)
    assert "Ben Das" in admin.get("/circulation/history?status=issued").get_data(as_text=True)
