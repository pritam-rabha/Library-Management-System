from datetime import datetime, timezone

from flask import Blueprint, Response, flash, redirect, render_template, request, session, url_for

from ..services import backup as service
from ..services.errors import BackupError
from . import get_store

bp = Blueprint("backup", __name__, url_prefix="/backup")


@bp.route("/")
def index():
    return render_template("backup/index.html", counts=service.summary(get_store().read()))


@bp.route("/export")
def export():
    payload = service.build_backup(get_store().read())
    import json
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    name = "library-backup-%s.json" % datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(body, mimetype="application/json",
                    headers={"Content-Disposition": 'attachment; filename="%s"' % name})


@bp.route("/validate", methods=["POST"])
def validate():
    upload = request.files.get("backup_file")
    if upload is None or not upload.filename:
        flash("Choose a backup file to validate.", "danger")
        return redirect(url_for("backup.index"))
    store = get_store()
    try:
        clean, exported_at = service.parse_backup(upload.read())
    except BackupError as exc:
        return render_template("backup/index.html", counts=service.summary(store.read()),
                               problems=exc.problems[:25], more=max(0, len(exc.problems) - 25),
                               filename=upload.filename), 400
    token = service.stage_backup(store, clean)
    session["restore_token"] = token
    return render_template("backup/confirm.html", token=token, incoming=service.summary(clean),
                           current=service.summary(store.read()), exported_at=exported_at,
                           filename=upload.filename)


@bp.route("/restore", methods=["POST"])
def restore():
    token = request.form.get("token", "")
    if request.form.get("confirm") != "yes":
        flash("Restore cancelled: you must tick the confirmation box.", "danger")
        return redirect(url_for("backup.index"))
    if token != session.get("restore_token"):
        flash("The restore request is invalid or has expired. Upload the file again.", "danger")
        return redirect(url_for("backup.index"))
    try:
        clean = service.restore(get_store(), token)
    except BackupError as exc:
        flash(exc.problems[0], "danger")
        return redirect(url_for("backup.index"))
    session.pop("restore_token", None)
    flash("Backup restored: %d books, %d members, %d transactions. A copy of the previous data was kept "
          "as library.pre-restore.json." % (len(clean["books"]), len(clean["members"]), len(clean["transactions"])),
          "success")
    return redirect(url_for("main.dashboard"))
