"""Blueprint modul Forum (url_prefix diatur di app/__init__.py)."""
from flask import Blueprint

bp = Blueprint("forum", __name__)

from . import routes  # noqa: E402,F401
