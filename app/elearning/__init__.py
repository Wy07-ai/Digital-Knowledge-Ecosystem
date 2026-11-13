"""Blueprint modul E-Learning (url_prefix diatur di app/__init__.py)."""
from flask import Blueprint

bp = Blueprint("elearning", __name__)

from . import routes  # noqa: E402,F401
