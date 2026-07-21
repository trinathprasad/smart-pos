from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _safe_next_url():
    next_url = request.args.get("next") or ""
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return url_for("main.index")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_logged_in"):
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if (
            username == current_app.config["ADMIN_USERNAME"]
            and password == current_app.config["ADMIN_PASSWORD"]
        ):
            session.clear()
            session["admin_logged_in"] = True
            session["admin_username"] = username
            flash("Logged in successfully.", "success")
            return redirect(_safe_next_url())

        flash("Invalid username or password.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("auth.login"))
