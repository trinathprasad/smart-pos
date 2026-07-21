from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .utils import format_bill_datetime, format_quantity_with_unit


PINK = colors.HexColor("#d91b8c")
DARK = colors.HexColor("#222222")
LIGHT = colors.HexColor("#f4f8f8")
MUTED = colors.HexColor("#666666")
SYSTEM_FOOTER = "System-generated invoice | No signature required | Developed by @Trinath"


def _money(value) -> str:
    return f"Rs. {value:.2f}"


def _plain(value) -> str:
    return "" if value is None else str(value)


def _text(value) -> str:
    return escape(_plain(value))


def _draw_invoice_frame(canvas, doc):
    canvas.saveState()
    width, height = A4

    canvas.setFillColor(PINK)
    canvas.rect(0, height - 5 * mm, width, 5 * mm, stroke=0, fill=1)
    canvas.line(18 * mm, height - 21 * mm, 72 * mm, height - 21 * mm)
    canvas.setStrokeColor(PINK)
    canvas.setLineWidth(1.2)
    canvas.line(18 * mm, height - 23 * mm, 58 * mm, height - 23 * mm)

    canvas.setFillColor(PINK)
    canvas.rect(0, 0, width, 4 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 7)
    canvas.drawCentredString(width / 2, 1.25 * mm, SYSTEM_FOOTER)
    canvas.restoreState()


def build_invoice_pdf(shop, sale) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=sale.invoice_no,
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ShopName",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=20,
            textColor=DARK,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallText",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=DARK,
        )
    )
    styles.add(
        ParagraphStyle(
            name="InvoiceTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=30,
            alignment=TA_RIGHT,
            textColor=PINK,
        )
    )
    styles.add(
        ParagraphStyle(
            name="RightSmall",
            parent=styles["SmallText"],
            alignment=TA_RIGHT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Footer",
            parent=styles["SmallText"],
            alignment=TA_CENTER,
            textColor=MUTED,
        )
    )

    shop_lines = [Paragraph(_text(shop.shop_name), styles["ShopName"])]
    if shop.address:
        shop_lines.append(Paragraph(_text(shop.address), styles["SmallText"]))
    if shop.phone:
        shop_lines.append(Paragraph(f"Phone: {_text(shop.phone)}", styles["SmallText"]))

    invoice_lines = [
        Paragraph("INVOICE", styles["InvoiceTitle"]),
        Paragraph(f"<b>Invoice:</b> {_text(sale.invoice_no)}", styles["RightSmall"]),
        Paragraph(f"<b>Date:</b> {format_bill_datetime(sale.created_at)}", styles["RightSmall"]),
        Paragraph(f"<b>Customer:</b> {_text(sale.customer_name) or 'Walk-in Customer'}", styles["RightSmall"]),
        Paragraph(f"<b>Payment:</b> {_text(sale.payment_status)} by {_text(sale.payment_mode)}", styles["RightSmall"]),
    ]
    if sale.payment_reference:
        invoice_lines.append(Paragraph(f"<b>Details:</b> {_text(sale.payment_reference)}", styles["RightSmall"]))

    story = [
        Table(
            [[shop_lines, invoice_lines]],
            colWidths=[100 * mm, 74 * mm],
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 14),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                ]
            ),
        ),
        Spacer(1, 5 * mm),
    ]

    item_data = [[
        Paragraph("<b>SL.</b>", styles["SmallText"]),
        Paragraph("<b>PRODUCT</b>", styles["SmallText"]),
        Paragraph("<b>PRICE</b>", styles["RightSmall"]),
        Paragraph("<b>QTY</b>", styles["RightSmall"]),
        Paragraph("<b>TOTAL</b>", styles["RightSmall"]),
    ]]

    for index, item in enumerate(sale.items, start=1):
        unit = item.product.unit if item.product else ""
        item_data.append(
            [
                Paragraph(f"{index:02d}", styles["SmallText"]),
                Paragraph(_text(item.product_name), styles["SmallText"]),
                Paragraph(_money(item.unit_price), styles["RightSmall"]),
                Paragraph(_text(format_quantity_with_unit(item.qty, unit)), styles["RightSmall"]),
                Paragraph(_money(item.line_total), styles["RightSmall"]),
            ]
        )

    item_table = Table(
        item_data,
        colWidths=[15 * mm, 82 * mm, 28 * mm, 20 * mm, 29 * mm],
        repeatRows=1,
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PINK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), LIGHT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT, colors.white]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ]
        ),
    )
    story.extend([item_table, Spacer(1, 8 * mm)])

    totals_data = [
        ["Subtotal:", _money(sale.subtotal)],
        ["Tax:", _money(sale.tax_amount)],
        ["Grand Total:", _money(sale.grand_total)],
    ]
    if sale.previous_pending_amount > 0:
        totals_data.extend(
            [
                ["Previous Pending Amount:", _money(sale.previous_pending_amount)],
                ["Total Payable:", _money(sale.total_payable)],
            ]
        )
    totals_data.extend(
        [
            ["Paid:", _money(sale.paid_amount)],
            [Paragraph("<b>Balance Due:</b>", styles["RightSmall"]), Paragraph(f"<b>{_money(sale.balance_due)}</b>", styles["RightSmall"])],
        ]
    )
    balance_row = len(totals_data) - 1

    totals_table = Table(
        totals_data,
        colWidths=[45 * mm, 35 * mm],
        hAlign="RIGHT",
        style=TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, balance_row - 1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LINEABOVE", (0, 0), (-1, 0), 0.8, DARK),
                ("LINEABOVE", (0, balance_row), (-1, balance_row), 0.6, colors.HexColor("#cccccc")),
                ("TEXTCOLOR", (1, balance_row), (1, balance_row), PINK),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        ),
    )
    story.extend([totals_table, Spacer(1, 18 * mm)])

    if shop.footer_note:
        story.append(Paragraph(_text(shop.footer_note), styles["Footer"]))

    doc.build(story, onFirstPage=_draw_invoice_frame, onLaterPages=_draw_invoice_frame)
    buffer.seek(0)
    return buffer
