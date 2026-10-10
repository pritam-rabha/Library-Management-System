import re

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.services import books, members

ADMIN_USER = "admin"
ADMIN_PASSWORD = "correct-horse-battery"


@pytest.fixture
def app(tmp_path):
    return create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key-for-unit-tests-only",
        "ADMIN_USERNAME": ADMIN_USER,
        "ADMIN_PASSWORD_HASH": generate_password_hash(ADMIN_PASSWORD, method="pbkdf2:sha256"),
        "DATA_FILE": str(tmp_path / "runtime" / "library.json"),
        "SEED_SAMPLE_DATA": False,
        "FINE_PER_DAY": "2.00",
        "LOAN_DAYS": 14,
        "MAX_LOANS_PER_MEMBER": 3,
        "SESSION_COOKIE_SECURE": False,
        "CURRENCY_SYMBOL": "Rs.",
    })


@pytest.fixture
def store(app):
    return app.extensions["store"]


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin(client):
    """A test client that is signed in as the administrator."""
    page = client.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    response = client.post("/login", data={"username": ADMIN_USER, "password": ADMIN_PASSWORD, "csrf_token": token})
    assert response.status_code == 302
    return client


@pytest.fixture
def post():
    """POST helper that adds the session's CSRF token."""
    def _post(client, url, data=None, **kwargs):
        with client.session_transaction() as sess:
            token = sess.setdefault("_csrf", "test-token")
        payload = dict(data or {})
        payload["csrf_token"] = token
        return client.post(url, data=payload, **kwargs)
    return _post


def book_form(**overrides):
    form = {"book_id": "B100", "title": "Test Driven Python", "author": "Mira Nair", "isbn": "",
            "category": "Technology", "publication_year": "2020", "total_copies": "2"}
    form.update(overrides)
    return form


def member_form(**overrides):
    form = {"member_id": "M100", "name": "Test Member", "email": "test.member@example.org",
            "phone": "", "member_type": "Student"}
    form.update(overrides)
    return form


@pytest.fixture
def library(store):
    """Three books and three members."""
    books.add_book(store, book_form(book_id="B001", title="Python Basics", author="Alice Smith", total_copies="2"))
    books.add_book(store, book_form(book_id="B002", title="Data Structures", author="Bob Jones", total_copies="1"))
    books.add_book(store, book_form(book_id="B003", title="Algorithms Unlocked", author="Alice Smith", total_copies="3"))
    members.add_member(store, member_form(member_id="M001", name="Asha Rao", email="asha@example.org"))
    members.add_member(store, member_form(member_id="M002", name="Ben Das", email="ben@example.org"))
    members.add_member(store, member_form(member_id="M003", name="Chitra Sen", email="chitra@example.org"))
    return store
