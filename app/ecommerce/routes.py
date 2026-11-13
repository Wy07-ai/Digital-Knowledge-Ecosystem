from flask import render_template

from . import bp


@bp.route("/")
def index():
    return render_template("ecommerce/index.html", page_title="E-Commerce")
