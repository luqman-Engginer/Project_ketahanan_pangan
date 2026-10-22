"""WSGI entrypoint: gunicorn -k gevent -w 1 wsgi:app."""
from __future__ import annotations

from flask import Flask

from app import create_app

app: Flask = create_app()
