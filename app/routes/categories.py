from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from PIL import Image, UnidentifiedImageError
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Category, Product
from ..schema import normalize_category_name


categories_bp = Blueprint("categories", __name__, url_prefix="/categories")
ALLOWED_CATEGORY_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
ALLOWED_CATEGORY_IMAGE_MIMETYPES = {"image/png", "image/jpeg"}
MAX_CATEGORY_IMAGE_UPLOAD_BYTES = 2 * 1024 * 1024
CATEGORY_IMAGE_FORMATS = {"PNG", "JPEG"}
CATEGORY_IMAGE_PREFIX = "uploads/category_images/"


def _validated_name(raw_name: str | None) -> tuple[str | None, str | None]:
    name = (raw_name or "").strip()
    if not name:
        return None, "Category name is required."
    if len(name) > 80:
        return None, "Category name cannot be longer than 80 characters."
    return name, None


def _validate_category_image(file_storage):
    filename = secure_filename(file_storage.filename or "")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_CATEGORY_IMAGE_EXTENSIONS or file_storage.mimetype not in ALLOWED_CATEGORY_IMAGE_MIMETYPES:
        return "Category image must be a PNG, JPG, or JPEG file."
    stream = file_storage.stream
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    if size > MAX_CATEGORY_IMAGE_UPLOAD_BYTES:
        return "Category image must be 2 MB or smaller."
    try:
        with Image.open(stream) as image:
            if image.format not in CATEGORY_IMAGE_FORMATS:
                return "Category image must be a PNG, JPG, or JPEG image."
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        return "The category image is not a valid PNG or JPEG image."
    finally:
        stream.seek(0)
    return None


def _save_category_image(file_storage):
    upload_dir = Path(current_app.static_folder) / "uploads" / "category_images"
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = secure_filename(file_storage.filename or "")
    extension = filename.rsplit(".", 1)[-1].lower()
    stored_filename = f"{uuid4().hex}.{extension}"
    image_file = upload_dir / stored_filename
    try:
        file_storage.save(image_file)
    except OSError:
        try:
            image_file.unlink(missing_ok=True)
        except OSError:
            current_app.logger.warning("Could not remove incomplete category image: %s", image_file)
        raise
    return f"{CATEGORY_IMAGE_PREFIX}{stored_filename}"


def _delete_category_image(image_path):
    if not image_path:
        return
    static_folder = Path(current_app.static_folder).resolve()
    image_file = (static_folder / image_path).resolve()
    upload_root = (static_folder / "uploads" / "category_images").resolve()
    if upload_root not in image_file.parents or not image_file.is_file():
        return
    if db.session.query(Category.id).filter(Category.image_path == image_path).first():
        return
    image_file.unlink()


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
        db.session.query(Product.category_id, db.func.count(db.distinct(Product.id)))
        .filter(Product.category_id.isnot(None), Product.is_active.is_(True))
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


@categories_bp.route("/<int:category_id>/products")
def category_products(category_id):
    category = Category.query.get_or_404(category_id)
    query = request.args.get("q", "").strip()
    category_products_query = Product.query.filter(
        Product.category_id == category.id,
        Product.is_active.is_(True),
    )
    total_products = category_products_query.count()
    product_query = category_products_query
    if query:
        like = f"%{query}%"
        product_query = product_query.filter(
            or_(Product.name.ilike(like), Product.sku.ilike(like))
        )
    products = product_query.order_by(Product.name.asc(), Product.sku.asc()).all()
    return render_template(
        "categories/products.html",
        category=category,
        products=products,
        query=query,
        total_products=total_products,
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
        image_file = request.files.get("image")
        has_new_image = bool(image_file and image_file.filename)
        if has_new_image:
            image_error = _validate_category_image(image_file)
            if image_error:
                flash(image_error, "danger")
                return _category_form()
        new_image_path = None
        try:
            if has_new_image:
                new_image_path = _save_category_image(image_file)
            db.session.add(Category(name=name, normalized_name=normalized_name, image_path=new_image_path))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            if new_image_path:
                try:
                    _delete_category_image(new_image_path)
                except OSError:
                    current_app.logger.warning("Could not remove failed category image: %s", new_image_path)
            flash("A category with that name already exists.", "danger")
            return _category_form()
        except (SQLAlchemyError, OSError):
            db.session.rollback()
            if new_image_path:
                try:
                    _delete_category_image(new_image_path)
                except OSError:
                    current_app.logger.warning("Could not remove failed category image: %s", new_image_path)
            flash("Category could not be saved. The existing category data was kept.", "danger")
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
        image_file = request.files.get("image")
        has_new_image = bool(image_file and image_file.filename)
        if has_new_image:
            image_error = _validate_category_image(image_file)
            if image_error:
                flash(image_error, "danger")
                return _category_form(category)
        old_image_path = category.image_path
        remove_image = request.form.get("remove_image") == "1"
        new_image_path = None
        try:
            if has_new_image:
                new_image_path = _save_category_image(image_file)
                category.image_path = new_image_path
            elif remove_image:
                category.image_path = None
            category.name = name
            category.normalized_name = normalized_name
            db.session.query(Product).filter(Product.category_id == category.id).update(
                {Product.category: name}, synchronize_session=False
            )
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            if new_image_path:
                try:
                    _delete_category_image(new_image_path)
                except OSError:
                    current_app.logger.warning("Could not remove failed category image: %s", new_image_path)
            flash("A category with that name already exists.", "danger")
            return _category_form(category)
        except (SQLAlchemyError, OSError):
            db.session.rollback()
            if new_image_path:
                try:
                    _delete_category_image(new_image_path)
                except OSError:
                    current_app.logger.warning("Could not remove failed category image: %s", new_image_path)
            flash("Category could not be saved. Your existing category image and data were kept.", "danger")
            return _category_form(category)
        if old_image_path and old_image_path != category.image_path:
            try:
                _delete_category_image(old_image_path)
            except OSError:
                current_app.logger.warning("Could not remove old category image: %s", old_image_path)
        flash("Category updated successfully.", "success")
        return redirect(url_for("categories.index"))
    return _category_form(category)


@categories_bp.route("/<int:category_id>/delete", methods=["POST"])
def delete(category_id):
    category = Category.query.get_or_404(category_id)
    active_assigned_count = Product.query.filter_by(category_id=category.id, is_active=True).count()
    if active_assigned_count:
        flash(
            f'Cannot delete "{category.name}" because {active_assigned_count} active product(s) are assigned to it. '
            "Reassign those products first.",
            "danger",
        )
        return redirect(url_for("categories.index"))

    old_image_path = category.image_path
    # Archived products are excluded from active category management. Clear only
    # their managed FK before deleting the category; retain the legacy text value
    # and the archived product records for backward compatibility and history.
    db.session.query(Product).filter(
        Product.category_id == category.id,
        Product.is_active.is_(False),
    ).update({Product.category_id: None}, synchronize_session=False)
    db.session.delete(category)
    db.session.commit()
    if old_image_path:
        try:
            _delete_category_image(old_image_path)
        except OSError:
            current_app.logger.warning("Could not remove deleted category image: %s", old_image_path)
    flash("Category deleted.", "info")
    return redirect(url_for("categories.index"))
