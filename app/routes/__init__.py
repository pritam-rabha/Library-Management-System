"""HTTP routes (thin layer over app.services)."""
from flask import current_app


def get_store():
    return current_app.extensions["store"]
