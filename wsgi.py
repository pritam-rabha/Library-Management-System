"""WSGI entry point: gunicorn wsgi:app"""
from app import create_app

app = create_app()

if __name__ == "__main__":  # python wsgi.py for a quick local run
    app.run(host="127.0.0.1", port=5000)
