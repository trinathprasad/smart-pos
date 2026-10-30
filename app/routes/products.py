import csv
from decimal import Decimal
from io import StringIO

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from sqlalchemy import and_, case, func, or_
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Category, Product, SaleItem
from ..utils import format_indian_number, to_decimal


products_bp = Blueprint("products", __name__, url_prefix="/products")


def _product_statistics():
    statistics = _inventory_statistics()
    return {
        "total_products": statistics["total_products"],
        "low_stock": statistics["low_stock"],
        "out_of_stock": statistics["out_of_stock"],
        "inventory_value": statistics["inventory_value"],
        "inventory_value_display": statistics["inventory_value_display"],
    }


def _inventory_statistics():
    total_products, total_units, low_stock, out_of_stock, inventory_value = (
        db.session.query(
            func.count(Product.id),
            func.coalesce(func.sum(Product.stock_qty), 0),
            func.coalesce(
                func.sum(case((and_(Product.stock_qty > 0, Product.stock_qty <= Product.low_stock_threshold), 1), else_=0)),
                0,
            ),
            func.coalesce(func.sum(case((Product.stock_qty <= 0, 1), else_=0)), 0),
            func.coalesce(func.sum(Product.purchase_price * Product.stock_qty), 0),
        )
        .filter(Product.is_active.is_(True))
        .one()
    )
    return {
        "total_products": total_products,
        "total_units": total_units,
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,
        "inventory_value": inventory_value,
        "inventory_value_display": format_indian_number(inventory_value),
    }


def _clean_barcode(value: str | None) -> str | None:
    barcode = (value or "").strip()
    return barcode or None


def _barcode_exists(barcode: str | None, product_id: int | None = None) -> bool:
    if not barcode:
        return False
    query = Product.query.filter(Product.barcode == barcode)
    if product_id is not None:
        query = query.filter(Product.id != product_id)
    return db.session.query(query.exists()).scalar()


def _active_categories():
    return Category.query.order_by(Category.name.asc()).all()


def _safe_return_path():
    return_to = request.values.get("return_to", "").strip()
    if return_to.startswith("/") and not return_to.startswith("//"):
        return return_to
    return None


def _render_product_form(product=None, selected_category_id=None):
    return render_template(
        "products/form.html",
        product=product,
        categories=_active_categories(),
        selected_category_id=selected_category_id,
        return_to=_safe_return_path(),
    )


def _category_from_form():
    raw_category_id = request.form.get("category_id", "").strip()
    if not raw_category_id:
        return None, None
    try:
        category_id = int(raw_category_id)
    except ValueError:
        return None, "Choose a valid category."
    category = db.session.get(Category, category_id)
    if category is None:
        return None, "Choose a valid category."
    return category, None


def _required_price(field_name: str, required_message: str):
    raw_value = request.form.get(field_name)
    if raw_value is None or raw_value.strip() == "":
        return None, required_message
    return to_decimal(raw_value), None


@products_bp.route("/")
def index():
    query = request.args.get("q", "").strip()
    sku_filter = request.args.get("sku", "").strip()
    name_filter = request.args.get("name", "").strip()
    category_filter = request.args.get("category", "").strip()
    selected_category = None
    if category_filter:
        if category_filter.isdigit():
            selected_category = db.session.get(Category, int(category_filter))
        if selected_category is None:
            normalized_filter = category_filter.casefold()
            selected_category = Category.query.filter_by(normalized_name=normalized_filter).first()
        if selected_category:
            category_filter = selected_category.name
    stock_filter = request.args.get("filter", "").strip().lower()
    sort = request.args.get("sort", "name").strip().lower()
    direction = request.args.get("direction", "asc").strip().lower()
    if stock_filter not in {"healthy", "low_stock", "out_of_stock"}:
        stock_filter = ""

    sort_columns = {
        "sku": Product.sku,
        "name": Product.name,
        "category": Category.name,
        "stock": Product.stock_qty,
        "purchase_price": Product.purchase_price,
        "selling_price": Product.selling_price,
    }
    if sort not in sort_columns:
        sort = "name"
    if direction not in {"asc", "desc"}:
        direction = "asc"

    product_query = Product.query.outerjoin(Category, Product.category_id == Category.id).filter(Product.is_active.is_(True))
    if query:
        like = f"%{query}%"
        search_columns = [Product.name, Product.sku, Product.category, Category.name]
        barcode_column = getattr(Product, "barcode", None)
        if barcode_column is not None:
            search_columns.append(barcode_column)
        product_query = product_query.filter(or_(*(column.ilike(like) for column in search_columns)))
    if sku_filter:
        product_query = product_query.filter(Product.sku.ilike(f"%{sku_filter}%"))
    if name_filter:
        product_query = product_query.filter(Product.name.ilike(f"%{name_filter}%"))
    if selected_category:
        product_query = product_query.filter(Product.category_id == selected_category.id)
    elif category_filter:
        product_query = product_query.filter(Product.category == category_filter)
    if stock_filter == "healthy":
        product_query = product_query.filter(Product.stock_qty > 0, Product.stock_qty > Product.low_stock_threshold)
    elif stock_filter == "low_stock":
        product_query = product_query.filter(Product.stock_qty > 0, Product.stock_qty <= Product.low_stock_threshold)
    elif stock_filter == "out_of_stock":
        product_query = product_query.filter(Product.stock_qty <= 0)

    sort_column = sort_columns[sort]
    order_expression = sort_column.desc() if direction == "desc" else sort_column.asc()
    product_query = product_query.order_by(order_expression, Product.name.asc())

    products = product_query.all()
    categories = Category.query.join(Product, Product.category_id == Category.id).filter(Product.is_active.is_(True)).distinct().order_by(Category.name.asc()).all()
    return render_template(
        "products/index.html",
        products=products,
        product_stats=_product_statistics(),
        categories=categories,
        query=query,
        sku_filter=sku_filter,
        name_filter=name_filter,
        category_filter=category_filter,
        stock_filter=stock_filter,
        sort=sort,
        direction=direction,
    )


@products_bp.route("/inventory")
def inventory():
    query = request.args.get("q", "").strip()
    category_filter = request.args.get("category", "").strip()
    stock_filter = request.args.get("filter", "").strip().lower()
    if stock_filter not in {"healthy", "low_stock", "out_of_stock"}:
        stock_filter = ""

    product_query = (
        Product.query.outerjoin(Category, Product.category_id == Category.id)
        .filter(Product.is_active.is_(True))
    )
    if query:
        like = f"%{query}%"
        product_query = product_query.filter(or_(Product.name.ilike(like), Product.sku.ilike(like)))
    if category_filter.isdigit():
        product_query = product_query.filter(Product.category_id == int(category_filter))
    elif category_filter:
        product_query = product_query.filter(Product.category == category_filter)
    if stock_filter == "healthy":
        product_query = product_query.filter(Product.stock_qty > 0, Product.stock_qty > Product.low_stock_threshold)
    elif stock_filter == "low_stock":
        product_query = product_query.filter(Product.stock_qty > 0, Product.stock_qty <= Product.low_stock_threshold)
    elif stock_filter == "out_of_stock":
        product_query = product_query.filter(Product.stock_qty <= 0)

    products = product_query.order_by(Product.name.asc(), Product.sku.asc()).all()
    categories = (
        Category.query.join(Product, Product.category_id == Category.id)
        .filter(Product.is_active.is_(True))
        .distinct()
        .order_by(Category.name.asc())
        .all()
    )
    return render_template(
        "products/inventory.html",
        products=products,
        inventory_stats=_inventory_statistics(),
        categories=categories,
        query=query,
        category_filter=category_filter,
        stock_filter=stock_filter,
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
                (product.category_record.name if product.category_record else product.category) or "",
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
        category, category_error = _category_from_form()
        if category_error:
            flash(category_error, "danger")
            return _render_product_form(None, request.form.get("category_id", type=int))
        sku = request.form.get("sku", "").strip()
        name = request.form.get("name", "").strip()
        barcode = _clean_barcode(request.form.get("barcode"))
        if not sku or not name:
            flash("SKU and product name are required.", "danger")
            return _render_product_form(None, request.form.get("category_id", type=int))
        if _barcode_exists(barcode):
            flash("Barcode already exists for another product.", "danger")
            return _render_product_form(None, request.form.get("category_id", type=int))
        purchase_price, price_error = _required_price("purchase_price", "Purchase price is required.")
        if price_error:
            flash(price_error, "danger")
            return _render_product_form(None, request.form.get("category_id", type=int))
        selling_price, price_error = _required_price("selling_price", "Selling price is required.")
        if price_error:
            flash(price_error, "danger")
            return _render_product_form(None, request.form.get("category_id", type=int))
        stock_qty = to_decimal(request.form.get("stock_qty"))
        low_stock_threshold = to_decimal(request.form.get("low_stock_threshold"))
        if purchase_price < 0:
            flash("Purchase price cannot be negative.", "danger")
            return _render_product_form(None, request.form.get("category_id", type=int))
        if selling_price < 0:
            flash("Selling price cannot be negative.", "danger")
            return _render_product_form(None, request.form.get("category_id", type=int))
        if stock_qty < 0 or low_stock_threshold < 0:
            flash("Stock and low stock values cannot be negative.", "danger")
            return _render_product_form(None, request.form.get("category_id", type=int))

        product = Product(
            sku=sku,
            barcode=barcode,
            name=name,
            category=category.name if category else None,
            category_record=category,
            brand=request.form.get("brand", "").strip() or None,
            unit=request.form.get("unit", "pcs").strip() or "pcs",
            description=request.form.get("description", "").strip() or None,
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
            if "barcode" in error_text:
                flash("Barcode already exists for another product.", "danger")
            elif "sku" in error_text or "unique constraint failed" in error_text:
                flash("SKU must be unique. This code already exists.", "danger")
            else:
                flash(f"Could not save product: {exc.orig}", "danger")
            return _render_product_form(None, request.form.get("category_id", type=int))
        flash("Product added successfully.", "success")
        return redirect(_safe_return_path() or url_for("products.index"))
    selected_category_id = request.args.get("category_id", type=int)
    return _render_product_form(None, selected_category_id)


@products_bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
def edit(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == "POST":
        category, category_error = _category_from_form()
        if category_error:
            flash(category_error, "danger")
            return _render_product_form(product, request.form.get("category_id", type=int))
        barcode = _clean_barcode(request.form.get("barcode"))
        if _barcode_exists(barcode, product.id):
            flash("Barcode already exists for another product.", "danger")
            return _render_product_form(product, request.form.get("category_id", type=int))
        purchase_price, price_error = _required_price("purchase_price", "Purchase price is required.")
        if price_error:
            flash(price_error, "danger")
            return _render_product_form(product, request.form.get("category_id", type=int))
        selling_price, price_error = _required_price("selling_price", "Selling price is required.")
        if price_error:
            flash(price_error, "danger")
            return _render_product_form(product, request.form.get("category_id", type=int))
        stock_qty = to_decimal(request.form.get("stock_qty"))
        low_stock_threshold = to_decimal(request.form.get("low_stock_threshold"))
        if purchase_price < 0:
            flash("Purchase price cannot be negative.", "danger")
            return _render_product_form(product, request.form.get("category_id", type=int))
        if selling_price < 0:
            flash("Selling price cannot be negative.", "danger")
            return _render_product_form(product, request.form.get("category_id", type=int))
        if stock_qty < 0 or low_stock_threshold < 0:
            flash("Stock and low stock values cannot be negative.", "danger")
            return _render_product_form(product, request.form.get("category_id", type=int))
        product.sku = request.form.get("sku", "").strip()
        product.barcode = barcode
        product.name = request.form.get("name", "").strip()
        product.category_record = category
        product.category = category.name if category else None
        product.brand = request.form.get("brand", "").strip() or None
        product.unit = request.form.get("unit", "pcs").strip() or "pcs"
        product.description = request.form.get("description", "").strip() or None
        product.purchase_price = purchase_price
        product.selling_price = selling_price
        product.stock_qty = stock_qty
        product.low_stock_threshold = low_stock_threshold
        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            error_text = str(exc.orig).lower()
            if "barcode" in error_text:
                flash("Barcode already exists for another product.", "danger")
            elif "sku" in error_text or "unique constraint failed" in error_text:
                flash("SKU must be unique. This code already exists.", "danger")
            else:
                flash(f"Could not update product: {exc.orig}", "danger")
            return _render_product_form(product, request.form.get("category_id", type=int))
        flash("Product updated successfully.", "success")
        return redirect(url_for("products.index"))
    return _render_product_form(product, request.form.get("category_id", type=int))


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
