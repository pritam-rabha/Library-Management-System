"""Authentication, CSRF, sessions, headers."""
import json
import re

from werkzeug.security import generate_password_hash

from app import create_app
from conftest import ADMIN_PASSWORD, ADMIN_USER


def login(client, username=ADMIN_USER, password=ADMIN_PASSWORD, next_url=""):
    page = client.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    return client.post("/login", data={"username": username, "password": password,
                                       "csrf_token": token, "next": next_url})


def test_pages_require_login(client):
    for url in ("/", "/books/", "/members/", "/circulation/issued", "/backup/", "/backup/export", "/settings"):
        response = client.get(url)
        assert response.status_code == 302 and "/login" in response.headers["Location"], url


def test_post_endpoints_require_login(client):
    with client.session_transaction() as sess:
        sess["_csrf"] = "tok"
    response = client.post("/books/B001/delete", data={"csrf_token": "tok"})
    assert response.status_code == 302 and "/login" in response.headers["Location"]


def test_successful_login_and_logout(client, post):
    assert login(client).status_code == 302
    assert client.get("/").status_code == 200
    response = post(client, "/logout")
    assert response.status_code == 302
    assert client.get("/").status_code == 302


def test_wrong_password_and_unknown_user_are_rejected(client):
    for creds in ({"password": "wrong-password"}, {"username": "root"}):
        response = login(client, **creds)
        assert response.status_code == 401
        assert "Incorrect username or password" in response.get_data(as_text=True)
    assert client.get("/").status_code == 302


def test_login_requires_csrf_token(client):
    client.get("/login")
    response = client.post("/login", data={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
    assert response.status_code == 400


def test_post_without_csrf_token_is_rejected(admin, library):
    response = admin.post("/books/B003/delete")
    assert response.status_code == 400
    response = admin.post("/books/B003/delete", data={"csrf_token": "forged"})
    assert response.status_code == 400
    assert admin.get("/books/B003").status_code == 200


def test_csrf_token_in_header_is_accepted(admin, library):
    with admin.session_transaction() as sess:
        token = sess["_csrf"]
    assert admin.post("/books/B003/delete", headers={"X-CSRFToken": token}).status_code == 302


def test_login_rotates_the_session(client):
    client.get("/login")
    with client.session_transaction() as sess:
        before = sess["_csrf"]
    login(client)
    with client.session_transaction() as sess:
        assert sess["_csrf"] != before and sess["admin"] == ADMIN_USER


def test_open_redirect_is_blocked(client):
    for target in ("https://evil.example/", "//evil.example", "/\\evil.example"):
        response = login(client, next_url=target)
        assert response.headers["Location"].endswith("/") and "evil" not in response.headers["Location"]
        client.get("/logout")
        with client.session_transaction() as sess:
            sess.clear()
    response = login(client, next_url="/books/")
    assert response.headers["Location"].endswith("/books/")


def test_login_is_throttled_after_repeated_failures(app, client):
    for _ in range(app.config["LOGIN_MAX_ATTEMPTS"]):
        assert login(client, password="bad-password").status_code == 401
    response = login(client)  # even the right password is refused while locked
    assert response.status_code == 429


def test_login_unavailable_without_configured_credentials(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "k" * 32, "ADMIN_USERNAME": "", "ADMIN_PASSWORD_HASH": "",
                      "DATA_FILE": str(tmp_path / "d.json"), "SEED_SAMPLE_DATA": False,
                      "SESSION_COOKIE_SECURE": False})
    assert login(app.test_client()).status_code == 503


def test_only_a_password_hash_is_configured_never_plaintext(app):
    stored = app.config["ADMIN_PASSWORD_HASH"]
    assert ADMIN_PASSWORD not in stored and stored.startswith("pbkdf2:")


def test_security_headers_and_cookie_flags(client):
    response = client.get("/login")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["Cache-Control"] == "no-store"
    cookie = response.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


def test_secure_cookie_and_hsts_in_production(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "p" * 32, "APP_ENV": "production", "ADMIN_USERNAME": "a",
                      "ADMIN_PASSWORD_HASH": generate_password_hash("x" * 12, method="pbkdf2:sha256"),
                      "DATA_FILE": str(tmp_path / "d.json"), "SEED_SAMPLE_DATA": False,
                      "SESSION_COOKIE_SECURE": True, "TRUST_PROXY": False})
    response = app.test_client().get("/login", base_url="https://localhost")
    assert "Secure" in response.headers["Set-Cookie"]
    assert "Strict-Transport-Security" in response.headers


def test_production_refuses_to_start_without_secret_key(tmp_path):
    import pytest
    with pytest.raises(RuntimeError):
        create_app({"APP_ENV": "production", "SECRET_KEY": None, "DATA_FILE": str(tmp_path / "d.json"),
                    "SEED_SAMPLE_DATA": False})


def test_health_check_is_public(client):
    response = client.get("/healthz")
    assert response.status_code == 200 and json.loads(response.get_data())["status"] == "ok"


def test_user_content_is_html_escaped(admin, post):
    post(admin, "/books/new", {"book_id": "XSS1", "title": "<img src=x onerror=alert(1)>", "author": "A. Uthor",
                               "total_copies": "1"})
    page = admin.get("/books/").get_data(as_text=True)
    assert "<img src=x" not in page and "&lt;img src=x" in page


def test_unknown_page_returns_friendly_404(admin):
    response = admin.get("/does-not-exist")
    assert response.status_code == 404 and "Page not found" in response.get_data(as_text=True)
