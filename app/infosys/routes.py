from flask import render_template

from . import bp


@bp.route("/")
def index():
    return render_template("infosys/index.html", page_title="Information System")
