"""Blueprint modul Information System (url_prefix diatur di app/__init__.py)."""
from flask import Blueprint

bp = Blueprint("infosys", __name__)

from . import routes  # noqa: E402,F401
