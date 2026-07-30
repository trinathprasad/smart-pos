from pathlib import Path

from flask import Flask, redirect, request, session, url_for
from sqlalchemy import inspect, text

from .config import Config
from .extensions import db
from .utils import format_bill_datetime, format_quantity, format_quantity_with_unit


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    app.jinja_env.filters["bill_datetime"] = format_bill_datetime
    app.jinja_env.filters["quantity"] = format_quantity
    app.jinja_env.filters["quantity_with_unit"] = format_quantity_with_unit

    @app.before_request
    def require_admin_login():
        if not app.config.get("AUTH_REQUIRED", False):
            return None

        public_endpoints = {"auth.login", "static"}
        if request.endpoint in public_endpoints or session.get("admin_logged_in"):
            return None
        next_url = request.full_path if request.query_string else request.path
        return redirect(url_for("auth.login", next=next_url))

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config["EXPORT_DIR"].mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    from .routes.auth import auth_bp
    from .routes.main import main_bp
    from .routes.products import products_bp
    from .routes.billing import billing_bp
    from .routes.customers import customers_bp
    from .routes.reports import reports_bp
    from .routes.settings import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)

    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        product_columns = {column["name"] for column in inspector.get_columns("product")}
        if "purchase_price" not in product_columns:
            db.session.execute(
                text("ALTER TABLE product ADD COLUMN purchase_price NUMERIC(10, 2) NOT NULL DEFAULT 0.00")
            )
        if "is_active" not in product_columns:
            db.session.execute(text("ALTER TABLE product ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"))
            db.session.commit()
        sale_item_columns = {column["name"] for column in inspector.get_columns("sale_item")}
        if "purchase_price" not in sale_item_columns:
            db.session.execute(
                text("ALTER TABLE sale_item ADD COLUMN purchase_price NUMERIC(10, 2) NOT NULL DEFAULT 0.00")
            )
        sale_columns = {column["name"] for column in inspector.get_columns("sale")}
        if "customer_id" not in sale_columns:
            db.session.execute(text("ALTER TABLE sale ADD COLUMN customer_id INTEGER"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_sale_customer_id ON sale (customer_id)"))
        if "payment_status" not in sale_columns:
            db.session.execute(text("ALTER TABLE sale ADD COLUMN payment_status VARCHAR(30) NOT NULL DEFAULT 'Paid'"))
        if "paid_amount" not in sale_columns:
            db.session.execute(text("ALTER TABLE sale ADD COLUMN paid_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00"))
        if "payment_reference" not in sale_columns:
            db.session.execute(text("ALTER TABLE sale ADD COLUMN payment_reference VARCHAR(120)"))
        if "previous_pending_amount" not in sale_columns:
            db.session.execute(
                text("ALTER TABLE sale ADD COLUMN previous_pending_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00")
            )
        shop_setting_columns = {column["name"] for column in inspector.get_columns("shop_setting")}
        if "logo_path" not in shop_setting_columns:
            db.session.execute(text("ALTER TABLE shop_setting ADD COLUMN logo_path VARCHAR(255)"))
        db.session.execute(
            text("UPDATE sale SET paid_amount = grand_total WHERE payment_status = 'Paid' AND paid_amount = 0")
        )
        db.session.commit()

    return app
