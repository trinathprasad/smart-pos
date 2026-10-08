from datetime import datetime
from decimal import Decimal

import csv
from io import StringIO

from flask import Blueprint, Response, render_template, request
from sqlalchemy import func

from ..models import Sale, SaleItem
from ..utils import format_bill_datetime, local_today, utc_bounds_for_local_date


reports_bp = Blueprint("reports", __name__, url_prefix="/reports")
def _report_date(value):
    if not value:
        return local_today()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return local_today()


def _daily_balance_due(sales):
    saved_customer_sales = {}
    walk_in_due = Decimal("0.00")

    for sale in sales:
        if sale.customer_id is None:
            walk_in_due += sale.balance_due
            continue
        saved_customer_sales.setdefault(sale.customer_id, []).append(sale)

    customer_due = Decimal("0.00")
    for customer_sales in saved_customer_sales.values():
        customer_sales.sort(key=lambda sale: sale.created_at)
        customer_due += customer_sales[0].previous_pending_amount
        customer_due += sum(
            (sale.grand_total - sale.paid_amount for sale in customer_sales),
            start=Decimal("0.00"),
        )

    return walk_in_due + customer_due


@reports_bp.route("/daily")
def daily():
    selected_date = request.args.get("date") or local_today().isoformat()
    report_date = _report_date(selected_date)
    selected_date = report_date.isoformat()
    start_of_day, end_of_day = utc_bounds_for_local_date(report_date)

    sales = (
        Sale.query.filter(Sale.created_at >= start_of_day, Sale.created_at <= end_of_day)
        .order_by(Sale.created_at.desc())
        .all()
    )
    top_items = (
        SaleItem.query.join(Sale)
        .with_entities(
            SaleItem.product_name,
            func.sum(SaleItem.qty).label("qty_sold"),
            func.sum(SaleItem.line_total).label("revenue"),
        )
        .filter(Sale.created_at >= start_of_day, Sale.created_at <= end_of_day)
        .group_by(SaleItem.product_name)
        .order_by(func.sum(SaleItem.line_total).desc())
        .limit(5)
        .all()
    )

    total_sales = sum((sale.grand_total for sale in sales), start=Decimal("0.00"))
    total_tax = sum((sale.tax_amount for sale in sales), start=Decimal("0.00"))
    total_due = _daily_balance_due(sales)
    total_profit = sum(
        (item.line_profit for sale in sales for item in sale.items),
        start=Decimal("0.00"),
    )
    return render_template(
        "reports/daily.html",
        sales=sales,
        selected_date=selected_date,
        total_sales=total_sales,
        total_tax=total_tax,
        total_due=total_due,
        total_profit=total_profit,
        top_items=top_items,
    )


@reports_bp.route("/daily/export")
def export_daily():
    selected_date = request.args.get("date") or local_today().isoformat()
    report_date = _report_date(selected_date)
    selected_date = report_date.isoformat()
    start_of_day, end_of_day = utc_bounds_for_local_date(report_date)
    sales = (
        Sale.query.filter(Sale.created_at >= start_of_day, Sale.created_at <= end_of_day)
        .order_by(Sale.created_at.asc())
        .all()
    )

    csv_buffer = StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(
        [
            "Invoice No",
            "Customer",
            "Payment Mode",
            "Payment Status",
            "Payment Details",
            "Created At",
            "Subtotal",
            "Tax",
            "Grand Total",
            "Previous Pending",
            "Paid Amount",
            "Balance Due",
        ]
    )
    for sale in sales:
        writer.writerow(
            [
                sale.invoice_no,
                sale.customer_name or "Walk-in",
                sale.payment_mode,
                sale.payment_status,
                sale.payment_reference or "",
                format_bill_datetime(sale.created_at),
                sale.subtotal,
                sale.tax_amount,
                sale.grand_total,
                sale.previous_pending_amount,
                sale.paid_amount,
                sale.balance_due,
            ]
        )
    filename = f"daily-sales-{selected_date}.csv"
    return Response(
        csv_buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
