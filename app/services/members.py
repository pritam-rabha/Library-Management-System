"""Member records."""
from .errors import ConflictError, NotFoundError, ValidationError
from .validators import clean_member, clean_text, normalize_id


def list_members(store, query=""):
    members = store.read()["members"]
    text = clean_text(query).lower()
    if text:
        members = [m for m in members
                   if text in m["name"].lower() or text in m["member_id"].lower() or text in m["email"]]
    return sorted(members, key=lambda m: m["name"].lower())


def get_member(store, member_id):
    member_id = normalize_id(member_id)
    for member in store.read()["members"]:
        if member["member_id"] == member_id:
            return member
    raise NotFoundError("Member %s was not found." % member_id)


def member_history(store, member_id):
    member_id = normalize_id(member_id)
    txns = [t for t in store.read()["transactions"] if t["member_id"] == member_id]
    return sorted(txns, key=lambda t: t["txn_id"], reverse=True)


def _has_active_loans(data, member_id):
    return any(t["member_id"] == member_id and t["return_date"] is None for t in data["transactions"])


def add_member(store, form):
    clean = clean_member(form)
    with store.transaction() as data:
        errors = {}
        if any(m["member_id"] == clean["member_id"] for m in data["members"]):
            errors["member_id"] = "A member with this ID already exists."
        if any(m["email"] == clean["email"] for m in data["members"]):
            errors["email"] = "A member with this email address already exists."
        if errors:
            raise ValidationError(errors)
        from . import clock
        clean["joined_date"] = clock.today().isoformat()
        data["members"].append(clean)
    return clean


def update_member(store, member_id, form):
    member_id = normalize_id(member_id)
    clean = clean_member(dict(form, member_id=member_id))
    with store.transaction() as data:
        member = next((m for m in data["members"] if m["member_id"] == member_id), None)
        if member is None:
            raise NotFoundError("Member %s was not found." % member_id)
        if any(m["email"] == clean["email"] and m is not member for m in data["members"]):
            raise ValidationError({"email": "Another member already uses this email address."})
        member.update(clean)
        for txn in data["transactions"]:  # keep the history label in step with the record
            if txn["member_id"] == member_id:
                txn["member_name"] = clean["name"]
        return dict(member)


def delete_member(store, member_id):
    member_id = normalize_id(member_id)
    with store.transaction() as data:
        member = next((m for m in data["members"] if m["member_id"] == member_id), None)
        if member is None:
            raise NotFoundError("Member %s was not found." % member_id)
        if _has_active_loans(data, member_id):
            raise ConflictError("This member still has books on loan. Record the returns before deleting.")
        data["members"].remove(member)
    return member
