"""Library settings (fine rate, loan period, loan limit) stored with the data."""
from .validators import clean_settings


def get_settings(store):
    return store.read()["settings"]


def update_settings(store, form):
    clean = clean_settings(form)
    with store.transaction() as data:
        data["settings"].update(clean)
    return clean
