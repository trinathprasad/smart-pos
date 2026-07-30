from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Numeric
from .extensions import db


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    category = db.Column(db.String(80), nullable=True, index=True)
    unit = db.Column(db.String(20), nullable=False, default="pcs")
    purchase_price = db.Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    selling_price = db.Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    stock_qty = db.Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    low_stock_threshold = db.Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    sale_items = db.relationship("SaleItem", back_populates="product")

    def is_low_stock(self) -> bool:
        return self.stock_qty <= self.low_stock_threshold




class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_no = db.Column(db.String(40), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=True, index=True)
    customer_name = db.Column(db.String(120), nullable=True)
    payment_mode = db.Column(db.String(30), nullable=False, default="Cash")
    payment_status = db.Column(db.String(30), nullable=False, default="Paid")
    paid_amount = db.Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    payment_reference = db.Column(db.String(120), nullable=True)
    subtotal = db.Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    tax_amount = db.Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    grand_total = db.Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    previous_pending_amount = db.Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    created_at = db.Column(db.DateTime,nullable=False,default=lambda: datetime.now(timezone.utc),)

    items = db.relationship(
        "SaleItem",
        back_populates="sale",
        cascade="all, delete-orphan",
        order_by="SaleItem.id",
    )
    customer = db.relationship("Customer", back_populates="sales")
    ledger_entries = db.relationship("CustomerLedger", back_populates="sale")

    @property
    def total_payable(self) -> Decimal:
        return self.grand_total + self.previous_pending_amount

    @property
    def balance_due(self) -> Decimal:
        return self.total_payable - self.paid_amount


class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sale.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    product_name = db.Column(db.String(120), nullable=False)
    qty = db.Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    purchase_price = db.Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    unit_price = db.Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    line_total = db.Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))

    sale = db.relationship("Sale", back_populates="items")
    product = db.relationship("Product", back_populates="sale_items")

    @property
    def cost_total(self) -> Decimal:
        return self.purchase_price * self.qty

    @property
    def line_profit(self) -> Decimal:
        return self.line_total - self.cost_total


class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=True, unique=True, index=True)
    address = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    sales = db.relationship("Sale", back_populates="customer")
    ledger_entries = db.relationship(
        "CustomerLedger",
        back_populates="customer",
        cascade="all, delete-orphan",
        order_by="CustomerLedger.created_at.desc()",
    )

    @property
    def balance_due(self) -> Decimal:
        return sum(
            (entry.debit_amount - entry.credit_amount for entry in self.ledger_entries),
            start=Decimal("0.00"),
        )


class CustomerLedger(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False, index=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sale.id"), nullable=True, index=True)
    entry_type = db.Column(db.String(30), nullable=False)
    debit_amount = db.Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    credit_amount = db.Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    note = db.Column(db.String(250), nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    customer = db.relationship("Customer", back_populates="ledger_entries")
    sale = db.relationship("Sale", back_populates="ledger_entries")


class ShopSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_name = db.Column(db.String(150), nullable=False, default="Local Shop Billing")
    logo_path = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    address = db.Column(db.Text, nullable=True)
    invoice_prefix = db.Column(db.String(20), nullable=False, default="INV")
    tax_percent = db.Column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    footer_note = db.Column(
        db.Text,
        nullable=False,
        default="Thank you for shopping with us.",
    )
    created_at = db.Column(db.DateTime,nullable=False,default=lambda: datetime.now(timezone.utc),)
    updated_at = db.Column(db.DateTime,nullable=False,default=lambda: datetime.now(timezone.utc),
                 onupdate=lambda: datetime.now(timezone.utc),)
    


def next_invoice_number(prefix: str = "INV") -> str:
    clean_prefix = (prefix or "INV").strip() or "INV"
    latest_sale = Sale.query.order_by(Sale.id.desc()).first()
    next_number = 1

    if latest_sale:
        latest_invoice = latest_sale.invoice_no or ""
        if latest_invoice.startswith(f"{clean_prefix}-"):
            suffix = latest_invoice.removeprefix(f"{clean_prefix}-")
            if suffix.isdigit():
                next_number = int(suffix) + 1
        else:
            next_number = latest_sale.id + 1

    return f"{clean_prefix}-{next_number:04d}"
