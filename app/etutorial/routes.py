from flask import render_template

from . import bp


@bp.route("/")
def index():
    return render_template("etutorial/index.html", page_title="E-Tutorial")
