"""Feature 4: add, view, edit and delete book and member records with validation."""
import pytest

from app.services import books, circulation, members
from app.services.errors import ConflictError, NotFoundError, ValidationError
from conftest import book_form, member_form


def test_add_book_sets_available_copies(store):
    book = books.add_book(store, book_form(book_id="b200", total_copies="4"))
    assert book["book_id"] == "B200"
    assert book["available_copies"] == 4
    assert books.get_book(store, "B200")["title"] == "Test Driven Python"


def test_add_and_view_book_through_the_web_form(admin, post):
    response = post(admin, "/books/new", book_form())
    assert response.status_code == 302 and response.headers["Location"].endswith("/books/B100")
    page = admin.get("/books/B100").get_data(as_text=True)
    assert "Test Driven Python" in page and "Mira Nair" in page
    assert "Test Driven Python" in admin.get("/books/").get_data(as_text=True)


@pytest.mark.parametrize("field,value", [
    ("book_id", ""), ("book_id", "x"), ("book_id", "bad id!"), ("book_id", "A" * 21),
    ("title", ""), ("title", "   "), ("title", "T" * 201),
    ("author", ""), ("isbn", "12345"), ("isbn", "abcdefghij"),
    ("publication_year", "20x0"), ("publication_year", "999"), ("publication_year", "3000"),
    ("total_copies", ""), ("total_copies", "0"), ("total_copies", "-3"), ("total_copies", "2.5"), ("total_copies", "1001"),
])
def test_invalid_book_input_is_rejected(store, field, value):
    with pytest.raises(ValidationError) as caught:
        books.add_book(store, book_form(**{field: value}))
    assert field in caught.value.errors
    assert store.read()["books"] == []


def test_duplicate_book_id_is_rejected_case_insensitively(library):
    with pytest.raises(ValidationError) as caught:
        books.add_book(library, book_form(book_id="b001"))
    assert "already exists" in caught.value.errors["book_id"]
    assert len(library.read()["books"]) == 3


def test_duplicate_book_id_shows_message_in_the_form(admin, post, library):
    response = post(admin, "/books/new", book_form(book_id="B001"))
    assert response.status_code == 400
    assert "A book with this ID already exists." in response.get_data(as_text=True)


def test_duplicate_isbn_is_rejected(store):
    books.add_book(store, book_form(isbn="978-93-5000-0017"))
    with pytest.raises(ValidationError) as caught:
        books.add_book(store, book_form(book_id="B101", isbn="9789350000017"))
    assert "isbn" in caught.value.errors


def test_edit_book_updates_fields_and_available_copies(library):
    circulation.issue_book(library, "B001", "M001")
    updated = books.update_book(library, "B001", book_form(title="Python Basics, 2nd Edition", total_copies="5"))
    assert updated["title"] == "Python Basics, 2nd Edition"
    assert updated["total_copies"] == 5 and updated["available_copies"] == 4


def test_edit_book_cannot_drop_total_below_issued_copies(library):
    circulation.issue_book(library, "B001", "M001")
    circulation.issue_book(library, "B001", "M002")
    with pytest.raises(ValidationError) as caught:
        books.update_book(library, "B001", book_form(total_copies="1"))
    assert "total_copies" in caught.value.errors
    assert books.get_book(library, "B001")["total_copies"] == 2


def test_edit_book_through_the_web_form(admin, post, library):
    response = post(admin, "/books/B002/edit", book_form(title="Data Structures Revised", total_copies="2"))
    assert response.status_code == 302
    assert books.get_book(library, "B002")["title"] == "Data Structures Revised"
    bad = post(admin, "/books/B002/edit", book_form(title=""))
    assert bad.status_code == 400 and "Title is required" in bad.get_data(as_text=True)


def test_delete_book(library):
    books.delete_book(library, "B003")
    with pytest.raises(NotFoundError):
        books.get_book(library, "B003")


def test_cannot_delete_book_with_issued_copies(library):
    circulation.issue_book(library, "B002", "M001")
    with pytest.raises(ConflictError):
        books.delete_book(library, "B002")
    assert books.get_book(library, "B002")["available_copies"] == 0


def test_delete_book_through_the_web(admin, post, library):
    response = post(admin, "/books/B003/delete")
    assert response.status_code == 302
    assert admin.get("/books/B003").status_code == 404


def test_history_survives_deleting_a_returned_book(library):
    txn = circulation.issue_book(library, "B003", "M001")
    circulation.return_book(library, txn["txn_id"])
    books.delete_book(library, "B003")
    history = members.member_history(library, "M001")
    assert history[0]["book_title"] == "Algorithms Unlocked"


# ---- members ---------------------------------------------------------
def test_add_view_edit_delete_member(store):
    member = members.add_member(store, member_form(member_id="m200"))
    assert member["member_id"] == "M200" and member["joined_date"]
    members.update_member(store, "M200", member_form(name="Renamed Member", phone="+91 98765 43210"))
    assert members.get_member(store, "M200")["name"] == "Renamed Member"
    members.delete_member(store, "M200")
    with pytest.raises(NotFoundError):
        members.get_member(store, "M200")


@pytest.mark.parametrize("field,value", [
    ("member_id", ""), ("member_id", "a"), ("member_id", "no spaces"),
    ("name", ""), ("name", "A"), ("email", ""), ("email", "not-an-email"), ("email", "a@b"),
    ("phone", "abc"), ("phone", "12"), ("member_type", "Alien"),
])
def test_invalid_member_input_is_rejected(store, field, value):
    with pytest.raises(ValidationError) as caught:
        members.add_member(store, member_form(**{field: value}))
    assert field in caught.value.errors


def test_duplicate_member_id_and_email_are_rejected(library):
    with pytest.raises(ValidationError) as caught:
        members.add_member(library, member_form(member_id="m001", email="other@example.org"))
    assert "member_id" in caught.value.errors
    with pytest.raises(ValidationError) as caught:
        members.add_member(library, member_form(member_id="M999", email="ASHA@example.org"))
    assert "email" in caught.value.errors


def test_cannot_delete_member_with_books_on_loan(library):
    circulation.issue_book(library, "B001", "M001")
    with pytest.raises(ConflictError):
        members.delete_member(library, "M001")


def test_member_web_pages(admin, post, library):
    assert post(admin, "/members/new", member_form()).status_code == 302
    assert "Test Member" in admin.get("/members/M100").get_data(as_text=True)
    assert post(admin, "/members/new", member_form()).status_code == 400
    assert post(admin, "/members/M100/edit", member_form(name="Edited Name")).status_code == 302
    assert "Edited Name" in admin.get("/members/").get_data(as_text=True)
    assert post(admin, "/members/M100/delete").status_code == 302
    assert admin.get("/members/M100").status_code == 404


def test_edit_member_name_updates_history_label(library):
    circulation.issue_book(library, "B001", "M001")
    members.update_member(library, "M001", member_form(member_id="M001", name="Asha R. Rao", email="asha@example.org"))
    assert members.member_history(library, "M001")[0]["member_name"] == "Asha R. Rao"
