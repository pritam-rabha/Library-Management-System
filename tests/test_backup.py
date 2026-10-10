"""Feature 6: backup export, validation, confirmed restore, protection against bad files."""
import io
import json

import pytest

from app.services import backup, books, circulation
from app.services.errors import BackupError


def export_payload(store):
    return backup.build_backup(store.read())


def as_bytes(payload):
    return json.dumps(payload).encode("utf-8")


def upload(client, post, payload_bytes, name="backup.json"):
    return post(client, "/backup/validate", {"backup_file": (io.BytesIO(payload_bytes), name)},
                content_type="multipart/form-data")


def test_export_downloads_valid_json_with_checksum(admin, library):
    response = admin.get("/backup/export")
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    payload = json.loads(response.get_data(as_text=True))
    assert payload["application"] == "Library Management System"
    assert len(payload["data"]["books"]) == 3 and len(payload["checksum_sha256"]) == 64
    clean, _ = backup.parse_backup(response.get_data())
    assert len(clean["members"]) == 3


def test_round_trip_restore_replaces_current_data(admin, post, library):
    circulation.issue_book(library, "B001", "M001")
    payload = export_payload(library)
    books.delete_book(library, "B003")
    assert len(library.read()["books"]) == 2

    page = upload(admin, post, as_bytes(payload))
    assert page.status_code == 200 and "Confirm restore" in page.get_data(as_text=True)
    assert len(library.read()["books"]) == 2  # nothing restored yet
    with admin.session_transaction() as sess:
        token = sess["restore_token"]
    done = post(admin, "/backup/restore", {"token": token, "confirm": "yes"}, follow_redirects=True)
    assert "Backup restored" in done.get_data(as_text=True)
    restored = library.read()
    assert len(restored["books"]) == 3 and len(restored["transactions"]) == 1
    assert books.get_book(library, "B001")["available_copies"] == 1
    assert library.path.with_name("library.pre-restore.json").exists()


def test_restore_requires_the_confirmation_box(admin, post, library):
    payload = export_payload(library)
    books.delete_book(library, "B003")
    upload(admin, post, as_bytes(payload))
    with admin.session_transaction() as sess:
        token = sess["restore_token"]
    response = post(admin, "/backup/restore", {"token": token}, follow_redirects=True)
    assert "you must tick the confirmation box" in response.get_data(as_text=True)
    assert len(library.read()["books"]) == 2


def test_restore_rejects_unknown_or_forged_tokens(admin, post, library):
    for token in ("../../etc/passwd", "short", "A" * 22, ""):
        response = post(admin, "/backup/restore", {"token": token, "confirm": "yes"}, follow_redirects=True)
        assert "invalid or has expired" in response.get_data(as_text=True)
    with pytest.raises(BackupError):
        backup.restore(library, "../secret")


@pytest.mark.parametrize("raw", [b"", b"not json at all", b"\xff\xfe\x00bad", b"[]", b"123", b'{"data": {}}'])
def test_garbage_files_are_rejected(admin, post, library, raw):
    response = upload(admin, post, raw)
    assert response.status_code == 400
    assert "rejected and nothing was changed" in response.get_data(as_text=True)
    assert len(library.read()["books"]) == 3


def test_modified_backup_fails_the_integrity_check(library):
    payload = export_payload(library)
    payload["data"]["books"][0]["title"] = "Tampered"
    with pytest.raises(BackupError) as caught:
        backup.parse_backup(as_bytes(payload))
    assert "integrity check failed" in caught.value.problems[0]


def test_wrong_application_or_version_is_rejected(library):
    payload = export_payload(library)
    with pytest.raises(BackupError):
        backup.parse_backup(as_bytes(dict(payload, application="Something Else")))
    with pytest.raises(BackupError):
        backup.parse_backup(as_bytes(dict(payload, format_version=99)))


def _resigned(data):
    return {"application": backup.APP_NAME, "format_version": 1, "exported_at": "x",
            "checksum_sha256": backup._checksum(data), "data": data}


def test_structurally_invalid_data_is_rejected_even_with_a_valid_checksum(library):
    base = library.read()
    cases = {}
    missing = dict(base); del missing["members"]; cases["missing section"] = missing
    dup = json.loads(json.dumps(base)); dup["books"].append(dict(dup["books"][0])); cases["duplicate id"] = dup
    bad_copy = json.loads(json.dumps(base)); bad_copy["books"][0]["available_copies"] = 99; cases["bad copies"] = bad_copy
    bad_field = json.loads(json.dumps(base)); bad_field["members"][0]["email"] = "nope"; cases["bad email"] = bad_field
    for label, data in cases.items():
        with pytest.raises(BackupError):
            backup.parse_backup(as_bytes(_resigned(data)))


def test_inconsistent_issue_records_are_rejected(library):
    circulation.issue_book(library, "B001", "M001")
    data = library.read()
    data["books"][0]["available_copies"] = 2  # an issued copy is not reflected
    with pytest.raises(BackupError) as caught:
        backup.parse_backup(as_bytes(_resigned(data)))
    assert any("do not match" in p for p in caught.value.problems)
    data = library.read()
    data["transactions"][0]["member_id"] = "GHOST"
    with pytest.raises(BackupError) as caught:
        backup.parse_backup(as_bytes(_resigned(data)))
    assert any("does not exist" in p for p in caught.value.problems)


def test_invalid_dates_and_fines_are_rejected(library):
    circulation.issue_book(library, "B001", "M001")
    for field, value in (("issue_date", "31-02-2026"), ("due_date", "2000-01-01"), ("fine", -5), ("overdue_days", "x")):
        data = library.read()
        data["transactions"][0][field] = value
        with pytest.raises(BackupError):
            backup.parse_backup(as_bytes(_resigned(data)))


def test_oversized_upload_is_refused(admin, post, library):
    response = upload(admin, post, b"{" + b" " * (3 * 1024 * 1024) + b"}")
    assert response.status_code in (302, 413)
    assert len(library.read()["books"]) == 3


def test_missing_file_is_reported(admin, post, library):
    response = post(admin, "/backup/validate", {}, follow_redirects=True)
    assert "Choose a backup file" in response.get_data(as_text=True)


def test_stale_staged_files_are_cleaned_up(library):
    import os, time
    clean, _ = backup.parse_backup(as_bytes(export_payload(library)))
    token = backup.stage_backup(library, clean)
    path = library.path.parent / "staging" / (token + ".json")
    os.utime(path, (time.time() - 7200, time.time() - 7200))
    backup.stage_backup(library, clean)
    assert not path.exists()
