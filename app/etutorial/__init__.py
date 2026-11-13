"""Blueprint modul E-Tutorial (url_prefix diatur di app/__init__.py)."""
from flask import Blueprint

bp = Blueprint("etutorial", __name__)

from . import routes  # noqa: E402,F401
