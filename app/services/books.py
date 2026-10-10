"""Book records and search."""
from .errors import ConflictError, NotFoundError, ValidationError
from .validators import clean_book, clean_text, normalize_id


def matches_query(book, query):
    """True when every word of the query occurs in the title or the author."""
    tokens = clean_text(query).lower().split()
    haystack = (book["title"] + " " + book["author"]).lower()
    return all(token in haystack for token in tokens)


def list_books(store, query="", category="", availability="all"):
    books = store.read()["books"]
    if query:
        books = [b for b in books if matches_query(b, query)]
    if category:
        books = [b for b in books if b.get("category", "") == category]
    if availability == "available":
        books = [b for b in books if b["available_copies"] > 0]
    elif availability == "unavailable":
        books = [b for b in books if b["available_copies"] == 0]
    return sorted(books, key=lambda b: b["title"].lower())


def categories(store):
    return sorted({b["category"] for b in store.read()["books"] if b.get("category")})


def get_book(store, book_id):
    book_id = normalize_id(book_id)
    for book in store.read()["books"]:
        if book["book_id"] == book_id:
            return book
    raise NotFoundError("Book %s was not found." % book_id)


def book_history(store, book_id):
    book_id = normalize_id(book_id)
    txns = [t for t in store.read()["transactions"] if t["book_id"] == book_id]
    return sorted(txns, key=lambda t: t["txn_id"], reverse=True)


def _active_count(data, book_id):
    return sum(1 for t in data["transactions"] if t["book_id"] == book_id and t["return_date"] is None)


def add_book(store, form):
    clean = clean_book(form)
    with store.transaction() as data:
        errors = {}
        if any(b["book_id"] == clean["book_id"] for b in data["books"]):
            errors["book_id"] = "A book with this ID already exists."
        if clean["isbn"] and any(b.get("isbn") == clean["isbn"] for b in data["books"]):
            errors["isbn"] = "A book with this ISBN already exists; increase its copies instead."
        if errors:
            raise ValidationError(errors)
        clean["available_copies"] = clean["total_copies"]
        data["books"].append(clean)
    return clean


def update_book(store, book_id, form):
    book_id = normalize_id(book_id)
    clean = clean_book(dict(form, book_id=book_id))
    with store.transaction() as data:
        book = next((b for b in data["books"] if b["book_id"] == book_id), None)
        if book is None:
            raise NotFoundError("Book %s was not found." % book_id)
        errors = {}
        if clean["isbn"] and any(b.get("isbn") == clean["isbn"] and b is not book for b in data["books"]):
            errors["isbn"] = "Another book already uses this ISBN."
        issued = _active_count(data, book_id)
        if clean["total_copies"] < issued:
            errors["total_copies"] = "%d cop%s currently issued; total copies cannot be lower." % (
                issued, "y is" if issued == 1 else "ies are")
        if errors:
            raise ValidationError(errors)
        book.update(clean)
        book["available_copies"] = clean["total_copies"] - issued
        return dict(book)


def delete_book(store, book_id):
    book_id = normalize_id(book_id)
    with store.transaction() as data:
        book = next((b for b in data["books"] if b["book_id"] == book_id), None)
        if book is None:
            raise NotFoundError("Book %s was not found." % book_id)
        if _active_count(data, book_id):
            raise ConflictError("This book has copies currently issued. Return them before deleting the record.")
        data["books"].remove(book)
    return book
