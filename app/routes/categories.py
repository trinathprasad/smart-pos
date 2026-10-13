from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Category, Product
from ..schema import normalize_category_name


categories_bp = Blueprint("categories", __name__, url_prefix="/categories")


def _validated_name(raw_name: str | None) -> tuple[str | None, str | None]:
    name = (raw_name or "").strip()
    if not name:
        return None, "Category name is required."
    if len(name) > 80:
        return None, "Category name cannot be longer than 80 characters."
    return name, None


def _category_form(category=None):
    return render_template("categories/form.html", category=category)


@categories_bp.route("/")
def index():
    query = request.args.get("q", "").strip()
    category_query = Category.query
    if query:
        category_query = category_query.filter(Category.name.ilike(f"%{query}%"))
    categories = category_query.order_by(Category.name.asc()).all()
    product_counts = dict(
        db.session.query(Product.category_id, db.func.count(Product.id))
        .filter(Product.category_id.isnot(None))
        .group_by(Product.category_id)
        .all()
    )
    total_assigned = sum(product_counts.values())
    return render_template(
        "categories/index.html",
        categories=categories,
        product_counts=product_counts,
        total_categories=Category.query.count(),
        total_assigned=total_assigned,
        query=query,
    )


@categories_bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        name, error = _validated_name(request.form.get("name"))
        if error:
            flash(error, "danger")
            return _category_form()
        normalized_name = normalize_category_name(name)
        if Category.query.filter_by(normalized_name=normalized_name).first():
            flash("A category with that name already exists.", "danger")
            return _category_form()
        try:
            db.session.add(Category(name=name, normalized_name=normalized_name))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("A category with that name already exists.", "danger")
            return _category_form()
        flash("Category added successfully.", "success")
        return redirect(url_for("categories.index"))
    return _category_form()


@categories_bp.route("/<int:category_id>/edit", methods=["GET", "POST"])
def edit(category_id):
    category = Category.query.get_or_404(category_id)
    if request.method == "POST":
        name, error = _validated_name(request.form.get("name"))
        if error:
            flash(error, "danger")
            return _category_form(category)
        normalized_name = normalize_category_name(name)
        duplicate = Category.query.filter(
            Category.normalized_name == normalized_name,
            Category.id != category.id,
        ).first()
        if duplicate:
            flash("A category with that name already exists.", "danger")
            return _category_form(category)
        category.name = name
        category.normalized_name = normalized_name
        try:
            db.session.query(Product).filter(Product.category_id == category.id).update(
                {Product.category: name}, synchronize_session=False
            )
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("A category with that name already exists.", "danger")
            return _category_form(category)
        flash("Category updated successfully.", "success")
        return redirect(url_for("categories.index"))
    return _category_form(category)


@categories_bp.route("/<int:category_id>/delete", methods=["POST"])
def delete(category_id):
    category = Category.query.get_or_404(category_id)
    assigned_count = Product.query.filter_by(category_id=category.id).count()
    if assigned_count:
        flash(
            f'Cannot delete "{category.name}" because {assigned_count} product(s) are assigned to it. '
            "Reassign those products first.",
            "danger",
        )
        return redirect(url_for("categories.index"))
    db.session.delete(category)
    db.session.commit()
    flash("Category deleted.", "info")
    return redirect(url_for("categories.index"))
