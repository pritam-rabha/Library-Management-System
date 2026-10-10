from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..services import members as service
from ..services.errors import ConflictError, ValidationError
from ..services.validators import MEMBER_TYPES
from . import get_store

bp = Blueprint("members", __name__, url_prefix="/members")


@bp.route("/")
def index():
    q = request.args.get("q", "")
    return render_template("members/list.html", members=service.list_members(get_store(), q), q=q)


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        try:
            member = service.add_member(get_store(), request.form)
        except ValidationError as exc:
            return render_template("members/form.html", mode="new", values=dict(request.form), errors=exc.errors,
                                   member_types=MEMBER_TYPES), 400
        flash("Member %s was added." % member["member_id"], "success")
        return redirect(url_for("members.detail", member_id=member["member_id"]))
    return render_template("members/form.html", mode="new", values={"member_type": "Student"}, errors={},
                           member_types=MEMBER_TYPES)


@bp.route("/<member_id>")
def detail(member_id):
    store = get_store()
    return render_template("members/detail.html", member=service.get_member(store, member_id),
                           history=service.member_history(store, member_id))


@bp.route("/<member_id>/edit", methods=["GET", "POST"])
def edit(member_id):
    store = get_store()
    member = service.get_member(store, member_id)
    if request.method == "POST":
        try:
            service.update_member(store, member_id, request.form)
        except ValidationError as exc:
            return render_template("members/form.html", mode="edit", member=member, values=dict(request.form),
                                   errors=exc.errors, member_types=MEMBER_TYPES), 400
        flash("Member %s was updated." % member["member_id"], "success")
        return redirect(url_for("members.detail", member_id=member["member_id"]))
    return render_template("members/form.html", mode="edit", member=member, values=member, errors={},
                           member_types=MEMBER_TYPES)


@bp.route("/<member_id>/delete", methods=["POST"])
def delete(member_id):
    try:
        member = service.delete_member(get_store(), member_id)
        flash("Member %s (%s) was deleted." % (member["member_id"], member["name"]), "success")
        return redirect(url_for("members.index"))
    except ConflictError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("members.detail", member_id=member_id))
