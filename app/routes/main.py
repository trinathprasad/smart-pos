from decimal import Decimal

from flask import Blueprint, render_template
from sqlalchemy import func

from ..models import Product, Sale, SaleItem
from ..utils import local_today, utc_bounds_for_local_date

main_bp = Blueprint("main", __name__)


def _sales_overview_chart_data():
    sale_day = func.date(Sale.created_at, "+5 hours", "+30 minutes")
    sales_by_day = (
        Sale.query
        .with_entities(
            sale_day.label("sale_day"),
            func.sum(Sale.grand_total).label("total_sales"),
        )
        .group_by(sale_day)
        .order_by(sale_day)
        .all()
    )

    return {
        "labels": [row.sale_day for row in sales_by_day],
        "values": [float(row.total_sales or 0) for row in sales_by_day],
        "emptyMessage": "No sales data available yet.",
    }


def _top_products_chart_data():
    quantity_sold = func.sum(SaleItem.qty)
    top_products = (
        SaleItem.query
        .with_entities(
            func.max(SaleItem.product_name).label("product_name"),
            quantity_sold.label("quantity_sold"),
        )
        .group_by(SaleItem.product_id)
        .order_by(quantity_sold.desc(), func.max(SaleItem.product_name).asc())
        .limit(5)
        .all()
    )

    return {
        "labels": [row.product_name for row in top_products],
        "values": [float(row.quantity_sold or 0) for row in top_products],
        "emptyMessage": "No product sales available.",
    }


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
        today_date=local_today().isoformat(),
        dashboard_chart_data={
            "salesOverview": _sales_overview_chart_data(),
            "topProducts": _top_products_chart_data(),
        },
    )
