from datetime import datetime, time, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo


TWOPLACES = Decimal("0.01")
LOCAL_TIMEZONE = ZoneInfo("Asia/Kolkata")


def to_decimal(value, default: str = "0.00") -> Decimal:
    try:
        return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def format_indian_number(value) -> str:
    amount = to_decimal(value)
    sign = "-" if amount < 0 else ""
    whole, fraction = f"{abs(amount):.2f}".split(".")
    if len(whole) > 3:
        leading = whole[:-3]
        trailing = whole[-3:]
        groups = []
        while len(leading) > 2:
            groups.insert(0, leading[-2:])
            leading = leading[:-2]
        if leading:
            groups.insert(0, leading)
        whole = f"{','.join(groups)},{trailing}"
    return f"{sign}{whole}.{fraction}"


def format_quantity(value) -> str:
    quantity = to_decimal(value)
    return format(quantity.normalize(), "f")


def format_quantity_with_unit(value, unit: str | None) -> str:
    return f"{format_quantity(value)}{(unit or '').strip()}"


def local_datetime(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LOCAL_TIMEZONE)


def format_bill_datetime(value) -> str:
    local_value = local_datetime(value)
    if local_value is None:
        return ""
    return local_value.strftime("%d %b %Y %I:%M %p")


def local_today():
    return datetime.now(LOCAL_TIMEZONE).date()


def utc_bounds_for_local_date(value):
    start_local = datetime.combine(value, time.min, tzinfo=LOCAL_TIMEZONE)
    end_local = datetime.combine(value, time.max, tzinfo=LOCAL_TIMEZONE)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        end_local.astimezone(timezone.utc).replace(tzinfo=None),
    )
