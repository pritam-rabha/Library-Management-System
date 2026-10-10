"""Input cleaning and validation shared by forms and backup validation."""
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from .errors import ValidationError

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,19}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9 -]{5,18}[0-9]$")
CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")
MEMBER_TYPES = ("Student", "Faculty", "Staff", "Guest")


def clean_text(value):
    """Collapse whitespace and strip control characters."""
    if value is None:
        return ""
    return " ".join(CTRL_RE.sub(" ", str(value)).split())


def normalize_id(value):
    return clean_text(value).upper()


def parse_int(value, low, high):
    """Return an int in [low, high] or None when the text is not a valid whole number."""
    text = clean_text(value)
    if not re.fullmatch(r"\d{1,6}", text):
        return None
    number = int(text)
    return number if low <= number <= high else None


def parse_money(value, maximum=Decimal("10000")):
    text = clean_text(value)
    if not re.fullmatch(r"\d{1,5}(\.\d{1,2})?", text):
        return None
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None
    return amount if amount <= maximum else None


def clean_book(form):
    errors = {}
    book_id = normalize_id(form.get("book_id"))
    if not ID_RE.match(book_id):
        errors["book_id"] = "Book ID must be 2 to 20 characters: letters, digits, hyphen or underscore."
    title = clean_text(form.get("title"))
    if not title or len(title) > 200:
        errors["title"] = "Title is required and must be at most 200 characters."
    author = clean_text(form.get("author"))
    if not author or len(author) > 120:
        errors["author"] = "Author is required and must be at most 120 characters."
    isbn_raw = clean_text(form.get("isbn"))
    isbn = ""
    if isbn_raw:
        digits = isbn_raw.replace("-", "").replace(" ", "")
        if re.fullmatch(r"\d{9}[\dXx]|\d{13}", digits):
            isbn = digits.upper()
        else:
            errors["isbn"] = "ISBN must contain 10 or 13 digits (hyphens allowed)."
    category = clean_text(form.get("category"))
    if len(category) > 60:
        errors["category"] = "Category must be at most 60 characters."
    year_raw = clean_text(form.get("publication_year"))
    year = None
    if year_raw:
        year = parse_int(year_raw, 1000, date.today().year + 1)
        if year is None:
            errors["publication_year"] = "Enter a valid four-digit year."
    copies = parse_int(form.get("total_copies"), 1, 1000)
    if copies is None:
        errors["total_copies"] = "Total copies must be a whole number from 1 to 1000."
    if errors:
        raise ValidationError(errors)
    return {"book_id": book_id, "title": title, "author": author, "isbn": isbn,
            "category": category, "publication_year": year, "total_copies": copies}


def clean_member(form):
    errors = {}
    member_id = normalize_id(form.get("member_id"))
    if not ID_RE.match(member_id):
        errors["member_id"] = "Member ID must be 2 to 20 characters: letters, digits, hyphen or underscore."
    name = clean_text(form.get("name"))
    if len(name) < 2 or len(name) > 100:
        errors["name"] = "Name is required (2 to 100 characters)."
    email = clean_text(form.get("email")).lower()
    if not EMAIL_RE.match(email) or len(email) > 120:
        errors["email"] = "Enter a valid email address."
    phone = clean_text(form.get("phone"))
    if phone and not PHONE_RE.match(phone):
        errors["phone"] = "Phone must contain 7 to 20 digits; spaces, hyphens and a leading + are allowed."
    member_type = clean_text(form.get("member_type")) or "Student"
    if member_type not in MEMBER_TYPES:
        errors["member_type"] = "Choose a valid member type."
    if errors:
        raise ValidationError(errors)
    return {"member_id": member_id, "name": name, "email": email, "phone": phone,
            "member_type": member_type}


def clean_settings(form):
    errors = {}
    fine = parse_money(form.get("fine_per_day"))
    if fine is None:
        errors["fine_per_day"] = "Fine per day must be a number from 0 to 10000 with at most two decimals."
    loan_days = parse_int(form.get("loan_days"), 1, 365)
    if loan_days is None:
        errors["loan_days"] = "Loan period must be a whole number of days from 1 to 365."
    max_loans = parse_int(form.get("max_loans_per_member"), 1, 50)
    if max_loans is None:
        errors["max_loans_per_member"] = "Maximum loans per member must be from 1 to 50."
    if errors:
        raise ValidationError(errors)
    return {"fine_per_day": float(fine), "loan_days": loan_days, "max_loans_per_member": max_loans}
