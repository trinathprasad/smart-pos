from flask import Blueprint, render_template


quick_actions_bp = Blueprint("quick_actions", __name__, url_prefix="/quick-actions")


@quick_actions_bp.route("/")
def index():
    return render_template("quick_actions/index.html")