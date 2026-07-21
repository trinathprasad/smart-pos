import csv
from io import StringIO

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Product, SaleItem
from ..utils import to_decimal


products_bp = Blueprint("products", __name__, url_prefix="/products")


@products_bp.route("/")
def index():
    query = request.args.get("q", "").strip()
    sku_filter = request.args.get("sku", "").strip()
    name_filter = request.args.get("name", "").strip()
    sort = request.args.get("sort", "name").strip().lower()
    direction = request.args.get("direction", "asc").strip().lower()

    sort_columns = {
        "sku": Product.sku,
        "name": Product.name,
    }
    if sort not in sort_columns:
        sort = "name"
    if direction not in {"asc", "desc"}:
        direction = "asc"

    product_query = Product.query.filter_by(is_active=True)
    if query:
        like = f"%{query}%"
        product_query = product_query.filter(
            or_(Product.name.ilike(like), Product.sku.ilike(like), Product.category.ilike(like))
        )
    if sku_filter:
        product_query = product_query.filter(Product.sku.ilike(f"%{sku_filter}%"))
    if name_filter:
        product_query = product_query.filter(Product.name.ilike(f"%{name_filter}%"))

    sort_column = sort_columns[sort]
    order_expression = sort_column.desc() if direction == "desc" else sort_column.asc()
    product_query = product_query.order_by(order_expression, Product.name.asc())

    products = product_query.all()
    return render_template(
        "products/index.html",
        products=products,
        query=query,
        sku_filter=sku_filter,
        name_filter=name_filter,
        sort=sort,
        direction=direction,
    )


@products_bp.route("/export")
def export():
    products = Product.query.filter_by(is_active=True).order_by(Product.name.asc()).all()
    csv_buffer = StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(
        ["SKU", "Name", "Category", "Unit", "Purchase Price", "Selling Price", "Stock Qty", "Low Stock Threshold"]
    )
    for product in products:
        writer.writerow(
            [
                product.sku,
                product.name,
                product.category or "",
                product.unit,
                product.purchase_price,
                product.selling_price,
                product.stock_qty,
                product.low_stock_threshold,
            ]
        )
    return Response(
        csv_buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=products.csv"},
    )


@products_bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        sku = request.form.get("sku", "").strip()
        name = request.form.get("name", "").strip()
        if not sku or not name:
            flash("SKU and product name are required.", "danger")
            return render_template("products/form.html", product=None)
        purchase_price = to_decimal(request.form.get("purchase_price"))
        selling_price = to_decimal(request.form.get("selling_price"))
        stock_qty = to_decimal(request.form.get("stock_qty"))
        low_stock_threshold = to_decimal(request.form.get("low_stock_threshold"))
        if purchase_price < 0 or selling_price < 0 or stock_qty < 0 or low_stock_threshold < 0:
            flash("Prices, stock, and low stock values cannot be negative.", "danger")
            return render_template("products/form.html", product=None)

        product = Product(
            sku=sku,
            name=name,
            category=request.form.get("category", "").strip() or None,
            unit=request.form.get("unit", "pcs").strip() or "pcs",
            purchase_price=purchase_price,
            selling_price=selling_price,
            stock_qty=stock_qty,
            low_stock_threshold=low_stock_threshold,
        )
        try:
            db.session.add(product)
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            error_text = str(exc.orig).lower()
            if "product.sku" in error_text or "unique constraint failed" in error_text:
                flash("SKU must be unique. This code already exists.", "danger")
            else:
                flash(f"Could not save product: {exc.orig}", "danger")
            return render_template("products/form.html", product=None)
        flash("Product added successfully.", "success")
        return redirect(url_for("products.index"))
    return render_template("products/form.html", product=None)


@products_bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
def edit(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == "POST":
        purchase_price = to_decimal(request.form.get("purchase_price"))
        selling_price = to_decimal(request.form.get("selling_price"))
        stock_qty = to_decimal(request.form.get("stock_qty"))
        low_stock_threshold = to_decimal(request.form.get("low_stock_threshold"))
        if purchase_price < 0 or selling_price < 0 or stock_qty < 0 or low_stock_threshold < 0:
            flash("Prices, stock, and low stock values cannot be negative.", "danger")
            return render_template("products/form.html", product=product)
        product.sku = request.form.get("sku", "").strip()
        product.name = request.form.get("name", "").strip()
        product.category = request.form.get("category", "").strip() or None
        product.unit = request.form.get("unit", "pcs").strip() or "pcs"
        product.purchase_price = purchase_price
        product.selling_price = selling_price
        product.stock_qty = stock_qty
        product.low_stock_threshold = low_stock_threshold
        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            error_text = str(exc.orig).lower()
            if "product.sku" in error_text or "unique constraint failed" in error_text:
                flash("SKU must be unique. This code already exists.", "danger")
            else:
                flash(f"Could not update product: {exc.orig}", "danger")
            return render_template("products/form.html", product=product)
        flash("Product updated successfully.", "success")
        return redirect(url_for("products.index"))
    return render_template("products/form.html", product=product)


@products_bp.route("/<int:product_id>/delete", methods=["POST"])
def delete(product_id):
    product = Product.query.get_or_404(product_id)
    sale_item_count = SaleItem.query.filter_by(product_id=product.id).count()
    if sale_item_count:
        product.is_active = False
        product.sku = f"{product.sku}-ARCHIVED-{product.id}"
        db.session.commit()
        flash(
            f"{product.name} is used in {sale_item_count} sale item(s), so it was archived instead.",
            "info",
        )
        return redirect(url_for("products.index"))

    db.session.delete(product)
    db.session.commit()
    flash("Product deleted.", "info")
    return redirect(url_for("products.index"))
