from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import re
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import ShopSetting

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")
ALLOWED_LOGO_EXTENSIONS = {"png", "jpg", "jpeg"}
ALLOWED_LOGO_MIMETYPES = {"image/png", "image/jpeg"}
MAX_LOGO_UPLOAD_BYTES = 2 * 1024 * 1024
PHONE_PATTERN = re.compile(r"^[0-9+(),\-\s]+$")
INVOICE_PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
SHOP_NAME_MAX_LENGTH = 150
PHONE_MAX_LENGTH = 30
ADDRESS_MAX_LENGTH = 1000
INVOICE_PREFIX_MAX_LENGTH = 20
FOOTER_NOTE_MAX_LENGTH = 1000


def _validate_logo(file_storage):
    filename = secure_filename(file_storage.filename or "")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_LOGO_EXTENSIONS or file_storage.mimetype not in ALLOWED_LOGO_MIMETYPES:
        return "Shop logo must be a PNG, JPG, or JPEG file."
    stream = file_storage.stream
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    if size > MAX_LOGO_UPLOAD_BYTES:
        return "Shop logo must be 2 MB or smaller."
    try:
        with Image.open(stream) as image:
            if image.format not in {"PNG", "JPEG"}:
                return "Shop logo must be a PNG, JPG, or JPEG image."
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        return "The shop logo is not a valid PNG or JPEG image."
    finally:
        stream.seek(0)
    return None


def _save_shop_logo(file_storage):
    upload_dir = Path(current_app.static_folder) / "uploads" / "shop_logos"
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = secure_filename(file_storage.filename or "")
    extension = filename.rsplit(".", 1)[-1].lower()
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


def _validate_shop_form(form):
    shop_name = form.get("shop_name", "").strip()
    phone = form.get("phone", "").strip()
    address = form.get("address", "").strip()
    invoice_prefix = form.get("invoice_prefix", "").strip()
    tax_value = form.get("tax_percent", "").strip()
    footer_note = form.get("footer_note", "")
    if not shop_name:
        return None, "Shop name is required."
    if len(shop_name) > SHOP_NAME_MAX_LENGTH:
        return None, f"Shop name must be {SHOP_NAME_MAX_LENGTH} characters or fewer."
    if len(phone) > PHONE_MAX_LENGTH or (phone and not PHONE_PATTERN.fullmatch(phone)):
        return None, "Phone may contain only numbers, spaces, commas, and + ( ) - characters."
    if len(address) > ADDRESS_MAX_LENGTH:
        return None, f"Address must be {ADDRESS_MAX_LENGTH} characters or fewer."
    if not invoice_prefix:
        return None, "Invoice prefix is required."
    if len(invoice_prefix) > INVOICE_PREFIX_MAX_LENGTH or not INVOICE_PREFIX_PATTERN.fullmatch(invoice_prefix):
        return None, "Invoice prefix may contain only letters, numbers, hyphens, and underscores."
    try:
        tax_percent = Decimal(tax_value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return None, "Tax percent must be a number between 0 and 100."
    if not tax_percent.is_finite() or tax_percent < 0 or tax_percent > 100:
        return None, "Tax percent must be between 0 and 100."
    if len(footer_note) > FOOTER_NOTE_MAX_LENGTH:
        return None, f"Invoice footer note must be {FOOTER_NOTE_MAX_LENGTH} characters or fewer."
    return {
        "shop_name": shop_name,
        "phone": phone,
        "address": address,
        "invoice_prefix": invoice_prefix.upper(),
        "tax_percent": tax_percent,
        "footer_note": footer_note,
    }, None


@settings_bp.route("/shop", methods=["GET", "POST"])
def shop():
    settings = ShopSetting.query.first()
    if settings is None:
        settings = ShopSetting()
        db.session.add(settings)
        db.session.commit()

    if request.method == "POST":
        form_values, validation_error = _validate_shop_form(request.form)
        if validation_error:
            flash(validation_error, "danger")
            return render_template("settings/shop.html", settings=settings)
        logo_file = request.files.get("shop_logo")
        has_new_logo = bool(logo_file and logo_file.filename)
        if has_new_logo:
            logo_error = _validate_logo(logo_file)
            if logo_error:
                flash(logo_error, "danger")
                return render_template("settings/shop.html", settings=settings)

        old_logo_path = settings.logo_path
        new_logo_path = None
        remove_logo = request.form.get("remove_shop_logo") == "1"
        try:
            if has_new_logo:
                new_logo_path = _save_shop_logo(logo_file)
                settings.logo_path = new_logo_path
            elif remove_logo:
                settings.logo_path = None
            for field, value in form_values.items():
                setattr(settings, field, value)
            db.session.commit()
        except (SQLAlchemyError, OSError):
            db.session.rollback()
            if new_logo_path:
                try:
                    _delete_shop_logo(new_logo_path)
                except OSError:
                    current_app.logger.warning("Could not remove failed shop logo: %s", new_logo_path)
            flash("Shop settings could not be saved. Your existing logo and settings were kept.", "danger")
            return render_template("settings/shop.html", settings=settings)

        if old_logo_path and old_logo_path != settings.logo_path:
            try:
                _delete_shop_logo(old_logo_path)
            except OSError:
                current_app.logger.warning("Could not remove old shop logo: %s", old_logo_path)
        flash("Shop settings updated.", "success")
        return redirect(url_for("settings.shop"))
    return render_template("settings/shop.html", settings=settings)
