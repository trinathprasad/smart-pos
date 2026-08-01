from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func

from .models import Sale, SaleItem
from .utils import local_today, utc_bounds_for_local_date


def _sale_total_between(start, end):
    return (
        Sale.query
        .with_entities(func.coalesce(func.sum(Sale.grand_total), 0))
        .filter(Sale.created_at >= start, Sale.created_at <= end)
        .scalar()
    ) or Decimal("0.00")


def _profit_total_between(start, end):
    profit_total = (
        SaleItem.query
        .join(Sale)
        .with_entities(
            func.coalesce(
                func.sum(SaleItem.line_total - (SaleItem.purchase_price * SaleItem.qty)),
                0,
            )
        )
        .filter(Sale.created_at >= start, Sale.created_at <= end)
        .scalar()
    )
    return profit_total or Decimal("0.00")


def _comparison_percent(today_value, yesterday_value):
    if yesterday_value == 0:
        return None

    return ((today_value - yesterday_value) / yesterday_value) * Decimal("100")


def dashboard_kpi_comparisons():
    today = local_today()
    yesterday = today - timedelta(days=1)

    today_start, today_end = utc_bounds_for_local_date(today)
    yesterday_start, yesterday_end = utc_bounds_for_local_date(yesterday)

    revenue_today = _sale_total_between(today_start, today_end)
    revenue_yesterday = _sale_total_between(yesterday_start, yesterday_end)
    profit_today = _profit_total_between(today_start, today_end)
    profit_yesterday = _profit_total_between(yesterday_start, yesterday_end)

    return {
        "revenue": _comparison_percent(revenue_today, revenue_yesterday),
        "profit": _comparison_percent(profit_today, profit_yesterday),
    }
