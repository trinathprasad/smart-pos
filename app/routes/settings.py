from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import ShopSetting
from ..utils import to_decimal


settings_bp = Blueprint("settings", __name__, url_prefix="/settings")
ALLOWED_LOGO_EXTENSIONS = {"png", "jpg", "jpeg"}
ALLOWED_LOGO_MIMETYPES = {"image/png", "image/jpeg"}


def _save_shop_logo(file_storage):
    filename = secure_filename(file_storage.filename or "")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_LOGO_EXTENSIONS or file_storage.mimetype not in ALLOWED_LOGO_MIMETYPES:
        return None

    upload_dir = Path(current_app.static_folder) / "uploads" / "shop_logos"
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4().hex}.{extension}"
    file_storage.save(upload_dir / stored_filename)
    return f"uploads/shop_logos/{stored_filename}"


def _delete_shop_logo(logo_path):
    if not logo_path:
        return

    static_folder = Path(current_app.static_folder).resolve()
    logo_file = (static_folder / logo_path).resolve()
    upload_root = (static_folder / "uploads" / "shop_logos").resolve()
    if upload_root in logo_file.parents and logo_file.is_file():
        logo_file.unlink()


@settings_bp.route("/shop", methods=["GET", "POST"])
def shop():
    settings = ShopSetting.query.first()
    
    if settings is None:
       settings = ShopSetting()
       db.session.add(settings)
       db.session.commit()

    if request.method == "POST":
        tax_percent = to_decimal(request.form.get("tax_percent"))
        if tax_percent < 0:
            flash("Tax percent cannot be negative.", "danger")
            return render_template("settings/shop.html", settings=settings)
        if request.form.get("remove_shop_logo") == "1":
            _delete_shop_logo(settings.logo_path)
            settings.logo_path = None
        logo_file = request.files.get("shop_logo")
        if logo_file and logo_file.filename:
            logo_path = _save_shop_logo(logo_file)
            if logo_path is None:
                flash("Shop logo must be a PNG, JPG, or JPEG file.", "danger")
                return render_template("settings/shop.html", settings=settings)
            settings.logo_path = logo_path
        settings.shop_name = request.form.get("shop_name", "").strip() or settings.shop_name
        settings.address = request.form.get("address", "").strip()
        settings.phone = request.form.get("phone", "").strip()
        settings.invoice_prefix = request.form.get("invoice_prefix", "INV").strip() or "INV"
        settings.tax_percent = tax_percent
        settings.footer_note = request.form.get("footer_note", "").strip() or settings.footer_note
        db.session.commit()
        flash("Shop settings updated.", "success")
        return redirect(url_for("settings.shop"))
    return render_template("settings/shop.html", settings=settings)
