from decimal import Decimal

from flask import Blueprint, render_template

from ..models import Product, Sale
from ..utils import local_today, utc_bounds_for_local_date

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    start_of_day, end_of_day = utc_bounds_for_local_date(local_today())

    product_count = Product.query.count()
    low_stock_count = Product.query.filter(Product.stock_qty <= Product.low_stock_threshold).count()

    today_query = Sale.query.filter(Sale.created_at >= start_of_day, Sale.created_at <= end_of_day)
    sales_today = (
        today_query
        .order_by(Sale.created_at.desc())
        .limit(10)
        .all()
    )
    all_sales_today = today_query.all()

    revenue_today = sum((sale.grand_total for sale in all_sales_today), start=Decimal("0.00"))
    profit_today = sum(
        (item.line_profit for sale in all_sales_today for item in sale.items),
        start=Decimal("0.00"),
    )

    return render_template(
        "dashboard.html",
        product_count=product_count,
        low_stock_count=low_stock_count,
        revenue_today=revenue_today,
        profit_today=profit_today,
        sales_today=sales_today,
    )
