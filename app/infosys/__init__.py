"""Blueprint modul Information System (url_prefix diatur di app/__init__.py)."""
from flask import Blueprint

bp = Blueprint("infosys", __name__)

from . import routes  # noqa: E402,F401
from . import admin  # noqa: E402,F401  (UC-AD-01/02, prioritas C)
