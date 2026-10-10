"""JSON storage: atomic writes, corruption handling, sample data separation."""
import json
import os
from pathlib import Path
from unittest import mock

import pytest

from app import create_app
from app.services import books, seed, backup, circulation
from app.services.errors import StorageError
from app.storage import JsonStore
from conftest import book_form

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "sample" / "sample_data.json"


def test_writes_are_atomic_and_leave_no_temp_files(store):
    books.add_book(store, book_form())
    leftovers = [p.name for p in store.path.parent.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []
    assert json.loads(store.path.read_text(encoding="utf-8"))["books"][0]["book_id"] == "B100"


def test_previous_version_is_kept_as_backup_file(store):
    books.add_book(store, book_form())
    books.add_book(store, book_form(book_id="B101"))
    previous = json.loads(Path(str(store.path) + ".bak").read_text(encoding="utf-8"))
    assert [b["book_id"] for b in previous["books"]] == ["B100"]


def test_failed_write_keeps_the_old_file_intact(store):
    books.add_book(store, book_form())
    before = store.path.read_text(encoding="utf-8")
    with mock.patch("app.storage.os.replace", side_effect=OSError("disk full")):
        with pytest.raises(StorageError):
            books.add_book(store, book_form(book_id="B101"))
    assert store.path.read_text(encoding="utf-8") == before
    assert [p for p in store.path.parent.iterdir() if p.name.endswith(".tmp")] == []


def test_exception_inside_a_transaction_saves_nothing(store):
    books.add_book(store, book_form())
    with pytest.raises(RuntimeError):
        with store.transaction() as data:
            data["books"].clear()
            raise RuntimeError("boom")
    assert len(store.read()["books"]) == 1


def test_corrupted_file_raises_storage_error_and_is_not_overwritten(store):
    store.read()
    store.path.write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(StorageError):
        store.read()
    with pytest.raises(StorageError):
        books.add_book(store, book_form())
    assert store.path.read_text(encoding="utf-8") == "{ this is not json"


def test_wrong_structure_is_treated_as_corruption(store):
    store.read()
    store.path.write_text(json.dumps({"books": "nope"}), encoding="utf-8")
    with pytest.raises(StorageError):
        store.read()


def test_web_shows_a_friendly_page_when_storage_is_corrupted(admin, store):
    store.path.write_text("garbage", encoding="utf-8")
    response = admin.get("/books/")
    assert response.status_code == 503 and "corrupted" in response.get_data(as_text=True)


def test_missing_data_file_is_created_empty(tmp_path):
    store = JsonStore(tmp_path / "new" / "data.json", lambda: {"settings": {}, "books": [], "members": [], "transactions": []})
    assert store.read()["books"] == [] and (tmp_path / "new" / "data.json").exists()


def test_sample_data_is_a_valid_dataset(app):
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    data = seed.build_from_sample(sample, app.config)
    clean, problems = backup.validate_dataset(data)
    assert problems == []
    assert len(data["books"]) >= 15 and len(data["members"]) >= 8
    assert any(t["return_date"] is None for t in data["transactions"])
    assert any(t["fine"] > 0 for t in data["transactions"])


def test_seeding_writes_runtime_file_and_never_touches_the_sample_file(tmp_path):
    before = SAMPLE.read_bytes()
    runtime = tmp_path / "runtime" / "library.json"
    app = create_app({"TESTING": True, "SECRET_KEY": "s" * 32, "DATA_FILE": str(runtime), "SEED_SAMPLE_DATA": True,
                      "SAMPLE_FILE": str(SAMPLE), "SESSION_COOKIE_SECURE": False})
    store = app.extensions["store"]
    assert runtime.exists() and runtime != SAMPLE
    assert len(store.read()["books"]) >= 15
    assert circulation.dashboard_stats(store)["overdue_books"] >= 1
    books.add_book(store, book_form())
    assert SAMPLE.read_bytes() == before


def test_unusable_sample_file_falls_back_to_an_empty_library(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("nope", encoding="utf-8")
    app = create_app({"TESTING": True, "SECRET_KEY": "s" * 32, "DATA_FILE": str(tmp_path / "r.json"),
                      "SEED_SAMPLE_DATA": True, "SAMPLE_FILE": str(bad), "SESSION_COOKIE_SECURE": False})
    assert app.extensions["store"].read()["books"] == []
