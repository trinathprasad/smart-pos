from datetime import datetime, timezone

from flask import Blueprint, flash, jsonify, redirect, render_template, request, send_file, url_for

from ..extensions import db
from ..models import Customer, CustomerLedger, Product, Sale, SaleItem, ShopSetting, next_invoice_number
from ..pdf import build_invoice_pdf
from ..utils import to_decimal


billing_bp = Blueprint("billing", __name__, url_prefix="/billing")
PAYMENT_STATUSES = {"Paid", "Pending", "Partial"}


@billing_bp.route("/new", methods=["GET", "POST"])
def new_bill():
    settings = ShopSetting.query.first()
    if settings is None:
        settings = ShopSetting()
        db.session.add(settings)
        db.session.commit()
        
    products = Product.query.filter_by(is_active=True).order_by(Product.name.asc()).all()
    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name.asc()).all()

    if request.method == "POST":
        product_ids = request.form.getlist("product_id[]")
        quantities = request.form.getlist("qty[]")
        customer_name = request.form.get("customer_name", "").strip() or None
        customer_id = request.form.get("customer_id", type=int)
        customer = Customer.query.get(customer_id) if customer_id else None
        payment_mode = request.form.get("payment_mode", "Cash").strip() or "Cash"
        payment_status = request.form.get("payment_status", "Paid").strip() or "Paid"
        payment_reference = request.form.get("payment_reference", "").strip() or None
        paid_amount_input = to_decimal(request.form.get("paid_amount"))
        previous_pending_amount = to_decimal(request.form.get("previous_pending_amount"))

        if customer_id and (customer is None or not customer.is_active):
            flash("Choose an active customer.", "danger")
            return render_template(
                "billing/new.html",
                products=products,
                customers=customers,
                settings=settings,
                draft_invoice=next_invoice_number(settings.invoice_prefix),
            )
        if customer:
            customer_name = customer.name
            previous_pending_amount = to_decimal("0")

        if payment_status not in PAYMENT_STATUSES:
            flash("Choose a valid payment status.", "danger")
            return render_template(
                "billing/new.html",
                products=products,
                customers=customers,
                settings=settings,
                draft_invoice=next_invoice_number(settings.invoice_prefix),
            )

        if previous_pending_amount < 0:
            flash("Previous pending amount cannot be negative.", "danger")
            return render_template(
                "billing/new.html",
                products=products,
                customers=customers,
                settings=settings,
                draft_invoice=next_invoice_number(settings.invoice_prefix),
            )

        sale = Sale(
            invoice_no=next_invoice_number(settings.invoice_prefix),
            customer=customer,
            customer_name=customer_name,
            payment_mode=payment_mode,
            payment_status=payment_status,
            payment_reference=payment_reference,
            previous_pending_amount=previous_pending_amount,
            created_at=datetime.now(timezone.utc),
        )

        subtotal = to_decimal("0")
        errors = []

        for product_id, qty_value in zip(product_ids, quantities, strict=False):
            if not product_id:
                continue
            qty = to_decimal(qty_value)
            product = Product.query.get(int(product_id))
            if product is None or not product.is_active or qty <= 0:
                continue
            if qty > product.stock_qty:
                errors.append(f"Insufficient stock for {product.name}.")
                continue

            line_total = to_decimal(product.selling_price * qty)
            sale.items.append(
                SaleItem(
                    product=product,
                    product_name=product.name,
                    qty=qty,
                    purchase_price=product.purchase_price,
                    unit_price=product.selling_price,
                    line_total=line_total,
                )
            )
            subtotal += line_total
            product.stock_qty = to_decimal(product.stock_qty - qty)

        if not sale.items:
            db.session.rollback()
            flash("Add at least one valid item to create a bill.", "danger")
            return render_template(
                "billing/new.html",
                products=products,
                customers=customers,
                settings=settings,
                draft_invoice=next_invoice_number(settings.invoice_prefix),
            )

        if errors:
            db.session.rollback()
            for error in errors:
                flash(error, "danger")
            return render_template(
                "billing/new.html",
                products=products,
                customers=customers,
                settings=settings,
                draft_invoice=next_invoice_number(settings.invoice_prefix),
            )

        tax_amount = to_decimal(subtotal * (settings.tax_percent / 100))
        sale.subtotal = subtotal
        sale.tax_amount = tax_amount
        sale.grand_total = subtotal + tax_amount
        if payment_status == "Paid":
            sale.paid_amount = sale.total_payable
        elif payment_status == "Pending":
            sale.paid_amount = to_decimal("0")
        else:
            if paid_amount_input <= 0 or paid_amount_input >= sale.total_payable:
                db.session.rollback()
                flash("For partial payment, paid amount must be more than 0 and less than total payable.", "danger")
                return render_template(
                    "billing/new.html",
                    products=products,
                    customers=customers,
                    settings=settings,
                    draft_invoice=next_invoice_number(settings.invoice_prefix),
                )
            sale.paid_amount = paid_amount_input

        if customer:
            db.session.add(
                CustomerLedger(
                    customer=customer,
                    sale=sale,
                    entry_type="bill",
                    debit_amount=sale.grand_total,
                    note=f"Bill {sale.invoice_no}",
                )
            )
            if sale.paid_amount > 0:
                db.session.add(
                    CustomerLedger(
                        customer=customer,
                        sale=sale,
                        entry_type="payment",
                        credit_amount=sale.paid_amount,
                        note=f"Payment for bill {sale.invoice_no}",
                    )
                )

        db.session.add(sale)
        db.session.commit()
        flash("Bill generated successfully.", "success")
        return redirect(url_for("billing.view_sale", sale_id=sale.id))

    draft_invoice = next_invoice_number(settings.invoice_prefix)
    return render_template(
        "billing/new.html",
        products=products,
        customers=customers,
        settings=settings,
        draft_invoice=draft_invoice,
    )


@billing_bp.route("/product-search")
def product_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    like = f"%{query}%"
    products = (
        Product.query.filter((Product.name.ilike(like)) | (Product.sku.ilike(like)))
        .filter_by(is_active=True)
        .order_by(Product.name.asc())
        .limit(10)
        .all()
    )
    return jsonify(
        [
            {
                "id": product.id,
                "sku": product.sku,
                "name": product.name,
                "price": float(product.selling_price),
                "stock_qty": float(product.stock_qty),
                "unit": product.unit,
            }
            for product in products
        ]
    )


@billing_bp.route("/sales/<int:sale_id>")
def view_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    settings = ShopSetting.query.first()
    return render_template("billing/invoice.html", sale=sale, settings=settings)


@billing_bp.route("/sales/<int:sale_id>/pdf")
def download_invoice(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    settings = ShopSetting.query.first()
    pdf = build_invoice_pdf(settings, sale)
    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{sale.invoice_no}.pdf",
    )
