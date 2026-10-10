from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..services import books as service
from ..services.errors import ConflictError, ValidationError
from . import get_store

bp = Blueprint("books", __name__, url_prefix="/books")


@bp.route("/")
def index():
    store = get_store()
    q = request.args.get("q", "")
    category = request.args.get("category", "")
    availability = request.args.get("availability", "all")
    rows = service.list_books(store, q, category, availability)
    return render_template("books/list.html", books=rows, q=q, category=category, availability=availability,
                           categories=service.categories(store))


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        try:
            book = service.add_book(get_store(), request.form)
        except ValidationError as exc:
            return render_template("books/form.html", mode="new", values=dict(request.form), errors=exc.errors), 400
        flash("Book %s was added." % book["book_id"], "success")
        return redirect(url_for("books.detail", book_id=book["book_id"]))
    return render_template("books/form.html", mode="new", values={"total_copies": 1}, errors={})


@bp.route("/<book_id>")
def detail(book_id):
    store = get_store()
    return render_template("books/detail.html", book=service.get_book(store, book_id),
                           history=service.book_history(store, book_id))


@bp.route("/<book_id>/edit", methods=["GET", "POST"])
def edit(book_id):
    store = get_store()
    book = service.get_book(store, book_id)
    if request.method == "POST":
        try:
            service.update_book(store, book_id, request.form)
        except ValidationError as exc:
            return render_template("books/form.html", mode="edit", book=book, values=dict(request.form),
                                   errors=exc.errors), 400
        flash("Book %s was updated." % book["book_id"], "success")
        return redirect(url_for("books.detail", book_id=book["book_id"]))
    return render_template("books/form.html", mode="edit", book=book, values=book, errors={})


@bp.route("/<book_id>/delete", methods=["POST"])
def delete(book_id):
    try:
        book = service.delete_book(get_store(), book_id)
        flash("Book %s (%s) was deleted." % (book["book_id"], book["title"]), "success")
        return redirect(url_for("books.index"))
    except ConflictError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("books.detail", book_id=book_id))
