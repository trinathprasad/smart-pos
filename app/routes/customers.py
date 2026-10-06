from decimal import Decimal
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Customer, CustomerLedger, Sale
from ..utils import format_indian_number, to_decimal


customers_bp = Blueprint("customers", __name__, url_prefix="/customers")
CUSTOMER_NAME_RE = re.compile(r"^[A-Za-z ]+$")
PHONE_RE = re.compile(r"^\d{10}$")


def customer_balance(customer: Customer) -> Decimal:
    return customer.balance_due


def _customer_statistics(customers: list[Customer]):
    balances = {customer.id: customer_balance(customer) for customer in customers}
    total_pending = sum(balances.values(), start=Decimal("0.00"))
    return {
        "total_customers": len(customers),
        "total_pending": total_pending,
        "total_pending_display": format_indian_number(total_pending),
        "no_pending": sum(1 for balance in balances.values() if balance == 0),
        "pending_customers": sum(1 for balance in balances.values() if balance > 0),
    }


def validate_customer_form(name: str, phone: str | None) -> bool:
    if not name:
        flash("Customer name is required.", "danger")
        return False
    if not CUSTOMER_NAME_RE.fullmatch(name):
        flash("Customer name should contain characters only.", "danger")
        return False
    if not phone:
        flash("Contact number is required.", "danger")
        return False
    if not PHONE_RE.fullmatch(phone):
        flash("Contact number should contain numbers only and must be exactly 10 digits.", "danger")
        return False
    return True

def active_customer_with_phone(phone: str, exclude_customer_id: int | None = None) -> Customer | None:
    query = Customer.query.filter_by(phone=phone, is_active=True)
    if exclude_customer_id is not None:
        query = query.filter(Customer.id != exclude_customer_id)
    return query.first()

@customers_bp.route("/")
def index():
    query = request.args.get("q", "").strip()
    balance_filter = request.args.get("filter", "").strip().lower()
    if balance_filter not in {"pending", "no_pending"}:
        balance_filter = ""

    active_customers = Customer.query.filter_by(is_active=True).all()
    customer_query = Customer.query.filter_by(is_active=True)
    if query:
        like = f"%{query}%"
        customer_query = customer_query.filter(
            or_(Customer.name.ilike(like), Customer.phone.ilike(like))
        )

    customers = customer_query.order_by(Customer.name.asc()).all()
    balances = {customer.id: customer_balance(customer) for customer in customers}
    if balance_filter == "pending":
        customers = [customer for customer in customers if balances[customer.id] > 0]
    elif balance_filter == "no_pending":
        customers = [customer for customer in customers if balances[customer.id] == 0]

    return render_template(
        "customers/index.html",
        customers=customers,
        customer_stats=_customer_statistics(active_customers),
        balances=balances,
        balance_filter=balance_filter,
        query=query,
    )


@customers_bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip() or None
        address = request.form.get("address", "").strip() or None
        form_data = {"name": name, "phone": phone, "address": address}
        if not validate_customer_form(name, phone):
            return render_template("customers/form.html", customer=None, form_data=form_data)
        if active_customer_with_phone(phone):
            flash("This phone number is already assigned to another customer.", "danger")
            return render_template("customers/form.html", customer=None, form_data=form_data)
        customer = Customer(name=name, phone=phone, address=address)
        try:
            db.session.add(customer)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("This phone number is already assigned to another customer.", "danger")
            return render_template("customers/form.html", customer=None, form_data=form_data)
        flash("Customer added successfully.", "success")
        return redirect(url_for("customers.detail", customer_id=customer.id))
    return render_template("customers/form.html", customer=None)


@customers_bp.route("/<int:customer_id>")
def detail(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    entries = CustomerLedger.query.filter_by(customer_id=customer.id).order_by(CustomerLedger.created_at.desc()).all()
    sales = Sale.query.filter_by(customer_id=customer.id).order_by(Sale.created_at.desc()).all()
    return render_template(
        "customers/detail.html",
        customer=customer,
        entries=entries,
        sales=sales,
        balance=customer_balance(customer),
    )


@customers_bp.route("/<int:customer_id>/edit", methods=["GET", "POST"])
def edit(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip() or None
        address = request.form.get("address", "").strip() or None
        form_data = {"name": name, "phone": phone, "address": address}
        if not validate_customer_form(name, phone):
            return render_template("customers/form.html", customer=customer, form_data=form_data)
        if active_customer_with_phone(phone, exclude_customer_id=customer.id):
            flash("This phone number is already assigned to another customer.", "danger")
            return render_template("customers/form.html", customer=customer, form_data=form_data)
        customer.name = name
        customer.phone = phone
        customer.address = address
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("This phone number is already assigned to another customer.", "danger")
            return render_template("customers/form.html", customer=customer, form_data=form_data)
        flash("Customer updated successfully.", "success")
        return redirect(url_for("customers.detail", customer_id=customer.id))
    return render_template("customers/form.html", customer=customer)


@customers_bp.route("/<int:customer_id>/ledger", methods=["POST"])
def add_ledger_entry(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    entry_type = request.form.get("entry_type", "").strip()
    amount = to_decimal(request.form.get("amount"))
    note = request.form.get("note", "").strip() or None
    balance = customer_balance(customer)

    if entry_type not in {"manual_due", "payment", "clear_balance"}:
        flash("Choose a valid balance action.", "danger")
    elif entry_type == "clear_balance":
        if balance <= 0:
            flash("This customer has no pending balance to clear.", "info")
        else:
            db.session.add(
                CustomerLedger(
                    customer=customer,
                    entry_type="clear_balance",
                    credit_amount=balance,
                    note=note or "Pending balance cleared.",
                )
            )
            db.session.commit()
            flash("Customer pending balance cleared.", "success")
    elif amount <= 0:
        flash("Enter an amount greater than zero.", "danger")
    elif entry_type == "payment" and amount > balance:
        flash("Payment cannot be greater than the pending balance.", "danger")
    else:
        db.session.add(
            CustomerLedger(
                customer=customer,
                entry_type=entry_type,
                debit_amount=amount if entry_type == "manual_due" else Decimal("0.00"),
                credit_amount=amount if entry_type == "payment" else Decimal("0.00"),
                note=note,
            )
        )
        db.session.commit()
        flash("Customer balance updated.", "success")
    return redirect(url_for("customers.detail", customer_id=customer.id))


@customers_bp.route("/<int:customer_id>/delete", methods=["POST"])
def delete(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if customer.sales or customer.ledger_entries:
        customer.archived_phone = customer.phone
        customer.phone = None
        customer.is_active = False
        db.session.commit()
        flash("Customer was deactivated because they have billing history.", "info")
    else:
        db.session.delete(customer)
        db.session.commit()
        flash("Customer deleted.", "info")
    return redirect(url_for("customers.index"))
