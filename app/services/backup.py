"""Backup export, validation and restore."""
import hashlib
import json
import re
import secrets
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from .errors import BackupError, ValidationError
from .validators import ID_RE, clean_book, clean_member, clean_settings

APP_NAME = "Library Management System"
FORMAT_VERSION = 1
MAX_RECORDS = 20000
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
STAGING_MAX_AGE = 3600


def _checksum(data):
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_backup(data):
    return {
        "application": APP_NAME,
        "format_version": FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checksum_sha256": _checksum(data),
        "data": data,
    }


def _iso(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def validate_dataset(raw):
    """Validate a full dataset. Returns (clean_data, problems)."""
    problems = []
    if not isinstance(raw, dict):
        return None, ["The backup data section must be an object."]
    for key in ("settings", "books", "members", "transactions"):
        if key not in raw:
            problems.append("Missing section: %s." % key)
    if problems:
        return None, problems
    if not isinstance(raw["settings"], dict) or not all(isinstance(raw[k], list) for k in ("books", "members", "transactions")):
        return None, ["The backup sections have the wrong types."]
    if any(len(raw[k]) > MAX_RECORDS for k in ("books", "members", "transactions")):
        return None, ["The backup contains too many records."]

    try:
        raw_settings = raw["settings"]
        settings = clean_settings({k: str(raw_settings.get(k, "")) for k in
                                   ("fine_per_day", "loan_days", "max_loans_per_member")})
    except ValidationError as exc:
        problems.extend("Settings: " + m for m in exc.errors.values())
        settings = None

    books, book_ids, isbns = [], set(), set()
    for index, rec in enumerate(raw["books"], start=1):
        label = "Book #%d" % index
        if not isinstance(rec, dict):
            problems.append("%s is not an object." % label)
            continue
        try:
            book = clean_book({k: ("" if rec.get(k) is None else str(rec.get(k))) for k in
                               ("book_id", "title", "author", "isbn", "category", "publication_year", "total_copies")})
        except ValidationError as exc:
            problems.extend("%s: %s" % (label, m) for m in exc.errors.values())
            continue
        if book["book_id"] in book_ids:
            problems.append("%s: duplicate book ID %s." % (label, book["book_id"]))
        if book["isbn"] and book["isbn"] in isbns:
            problems.append("%s: duplicate ISBN %s." % (label, book["isbn"]))
        book_ids.add(book["book_id"])
        isbns.add(book["isbn"])
        avail = rec.get("available_copies")
        if isinstance(avail, bool) or not isinstance(avail, int) or not 0 <= avail <= book["total_copies"]:
            problems.append("%s: available copies must be a whole number between 0 and total copies." % label)
            continue
        book["available_copies"] = avail
        books.append(book)

    members, member_ids, emails = [], set(), set()
    for index, rec in enumerate(raw["members"], start=1):
        label = "Member #%d" % index
        if not isinstance(rec, dict):
            problems.append("%s is not an object." % label)
            continue
        try:
            member = clean_member({k: ("" if rec.get(k) is None else str(rec.get(k))) for k in
                                   ("member_id", "name", "email", "phone", "member_type")})
        except ValidationError as exc:
            problems.extend("%s: %s" % (label, m) for m in exc.errors.values())
            continue
        if member["member_id"] in member_ids:
            problems.append("%s: duplicate member ID %s." % (label, member["member_id"]))
        if member["email"] in emails:
            problems.append("%s: duplicate email %s." % (label, member["email"]))
        member_ids.add(member["member_id"])
        emails.add(member["email"])
        joined = rec.get("joined_date")
        member["joined_date"] = joined if _iso(joined) else ""
        if joined and not _iso(joined):
            problems.append("%s: invalid joined date." % label)
        members.append(member)

    txns, txn_ids = [], set()
    active_per_book = {}
    for index, rec in enumerate(raw["transactions"], start=1):
        label = "Transaction #%d" % index
        if not isinstance(rec, dict):
            problems.append("%s is not an object." % label)
            continue
        txn_id = rec.get("txn_id")
        if not isinstance(txn_id, str) or not re.fullmatch(r"T\d{5,9}", txn_id):
            problems.append("%s: invalid transaction ID." % label)
            continue
        if txn_id in txn_ids:
            problems.append("%s: duplicate transaction ID %s." % (label, txn_id))
        txn_ids.add(txn_id)
        issued, due, returned = _iso(rec.get("issue_date")), _iso(rec.get("due_date")), _iso(rec.get("return_date"))
        if issued is None or due is None or due < issued:
            problems.append("%s: issue and due dates are invalid." % label)
            continue
        if rec.get("return_date") is not None and (returned is None or returned < issued):
            problems.append("%s: return date is invalid." % label)
            continue
        fine = rec.get("fine", 0)
        days = rec.get("overdue_days", 0)
        if isinstance(fine, bool) or not isinstance(fine, (int, float)) or fine < 0 or \
                isinstance(days, bool) or not isinstance(days, int) or days < 0:
            problems.append("%s: fine and overdue days must be non-negative numbers." % label)
            continue
        for field in ("book_id", "member_id"):
            if not isinstance(rec.get(field), str) or not ID_RE.match(rec[field]):
                problems.append("%s: invalid %s." % (label, field))
        if rec.get("return_date") is None:
            if rec.get("book_id") not in book_ids:
                problems.append("%s: issued book %s does not exist." % (label, rec.get("book_id")))
            if rec.get("member_id") not in member_ids:
                problems.append("%s: borrower %s does not exist." % (label, rec.get("member_id")))
            active_per_book[rec.get("book_id")] = active_per_book.get(rec.get("book_id"), 0) + 1
        txns.append({
            "txn_id": txn_id, "book_id": rec.get("book_id"),
            "book_title": str(rec.get("book_title", ""))[:200],
            "member_id": rec.get("member_id"), "member_name": str(rec.get("member_name", ""))[:100],
            "issue_date": rec["issue_date"], "due_date": rec["due_date"], "return_date": rec.get("return_date"),
            "overdue_days": days, "fine": round(float(fine), 2), "fine_per_day": rec.get("fine_per_day"),
        })

    for book in books:
        expected = book["total_copies"] - active_per_book.get(book["book_id"], 0)
        if expected < 0 or book["available_copies"] != expected:
            problems.append("Book %s: available copies do not match the issued records." % book["book_id"])

    if problems:
        return None, problems
    return {"settings": settings, "books": books, "members": members, "transactions": txns}, []


def parse_backup(raw_bytes):
    """Parse and fully validate an uploaded backup. Raises BackupError with every problem found."""
    if not raw_bytes:
        raise BackupError(["The file is empty."])
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise BackupError(["The file is not valid JSON text."])
    if not isinstance(payload, dict):
        raise BackupError(["The file does not look like a library backup."])
    if payload.get("application") != APP_NAME:
        raise BackupError(["The file was not created by this application."])
    if payload.get("format_version") != FORMAT_VERSION:
        raise BackupError(["Unsupported backup format version."])
    data = payload.get("data")
    checksum = payload.get("checksum_sha256")
    if not isinstance(checksum, str) or not isinstance(data, (dict, list)) or _checksum(data) != checksum:
        raise BackupError(["The integrity check failed: the file is damaged or was modified after export."])
    clean, problems = validate_dataset(data)
    if problems:
        raise BackupError(problems)
    return clean, payload.get("exported_at", "unknown")


def _staging_dir(store):
    path = store.path.parent / "staging"
    path.mkdir(parents=True, exist_ok=True)
    return path


def stage_backup(store, clean):
    """Save a validated dataset awaiting confirmation; returns a token."""
    directory = _staging_dir(store)
    now = time.time()
    for old in directory.glob("*.json"):
        if now - old.stat().st_mtime > STAGING_MAX_AGE:
            old.unlink(missing_ok=True)
    token = secrets.token_urlsafe(16)
    (directory / (token + ".json")).write_text(json.dumps(clean), encoding="utf-8")
    return token


def load_staged(store, token):
    if not isinstance(token, str) or not TOKEN_RE.match(token):
        raise BackupError(["The restore request is invalid or has expired. Upload the file again."])
    path = _staging_dir(store) / (token + ".json")
    try:
        clean = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise BackupError(["The restore request is invalid or has expired. Upload the file again."])
    clean, problems = validate_dataset(clean)
    if problems:
        raise BackupError(problems)
    return clean


def restore(store, token):
    """Replace the live data with the staged backup after re-validating it."""
    clean = load_staged(store, token)
    current = store.read()
    safety = store.path.with_name(store.path.stem + ".pre-restore.json")
    safety.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
    store.replace(clean)
    (_staging_dir(store) / (token + ".json")).unlink(missing_ok=True)
    return clean


def summary(clean):
    return {"books": len(clean["books"]), "members": len(clean["members"]),
            "transactions": len(clean["transactions"]),
            "issued": sum(1 for t in clean["transactions"] if t["return_date"] is None)}
