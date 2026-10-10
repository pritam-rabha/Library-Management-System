"""Feature 3: search books by title or author."""
import pytest

from app.services import books


def titles(rows):
    return [b["title"] for b in rows]


def test_search_by_title(library):
    assert titles(books.list_books(library, "python")) == ["Python Basics"]


def test_search_by_author_returns_all_of_their_books(library):
    assert titles(books.list_books(library, "alice smith")) == ["Algorithms Unlocked", "Python Basics"]


def test_search_is_case_insensitive_and_ignores_extra_spaces(library):
    assert titles(books.list_books(library, "   DATA    structures ")) == ["Data Structures"]


def test_search_matches_partial_words(library):
    assert titles(books.list_books(library, "algo")) == ["Algorithms Unlocked"]


def test_search_words_may_span_title_and_author(library):
    assert titles(books.list_books(library, "basics alice")) == ["Python Basics"]


@pytest.mark.parametrize("query", ["quantum", "zzz", "Python Jones"])
def test_search_with_no_match_returns_nothing(library, query):
    assert books.list_books(library, query) == []


def test_empty_query_lists_everything_sorted_by_title(library):
    assert titles(books.list_books(library, "")) == ["Algorithms Unlocked", "Data Structures", "Python Basics"]


def test_search_page_displays_matches_and_count(admin, library):
    page = admin.get("/books/?q=alice").get_data(as_text=True)
    assert "Python Basics" in page and "Algorithms Unlocked" in page
    assert "Data Structures" not in page
    assert "2 books found" in page


def test_search_page_explains_when_nothing_matches(admin, library):
    page = admin.get("/books/?q=nothing-like-this").get_data(as_text=True)
    assert "0 books found" in page and "No books match your search" in page


def test_search_input_is_escaped(admin, library):
    page = admin.get('/books/?q=<script>alert(1)</script>').get_data(as_text=True)
    assert "<script>alert(1)</script>" not in page


def test_category_and_availability_filters(admin, library, post):
    post(admin, "/circulation/issue", {"book_id": "B002", "member_id": "M001"})
    page = admin.get("/books/?availability=unavailable").get_data(as_text=True)
    assert "Data Structures" in page and "Python Basics" not in page


def test_header_search_form_points_to_book_search(admin):
    page = admin.get("/").get_data(as_text=True)
    assert 'action="/books/"' in page and 'name="q"' in page
