from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import ShopSetting
from ..utils import to_decimal


settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


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
