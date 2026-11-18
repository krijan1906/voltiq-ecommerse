"""Generate the diagrams used by the Voltiq project PDF manual.

The source canvases are 1400 px wide. At the PDF's 503 pt content width this
keeps labels at roughly 7-10 pt, which is comfortable on screen and in print.

Run from the repository root:
    .\\.venv\\Scripts\\python.exe docs/build_diagrams.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_generated" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)

NAVY = "#0B1220"
BLUE = "#2563EB"
BLUE_SOFT = "#E8F0FF"
AMBER = "#F59E0B"
AMBER_SOFT = "#FFF5E0"
GREEN = "#16A34A"
GREEN_SOFT = "#E9F9EF"
RED = "#DC2626"
RED_SOFT = "#FDECEC"
SLATE = "#475569"
MUTED = "#64748B"
LINE = "#CBD5E1"
CANVAS = "#F5F7FB"
WHITE = "#FFFFFF"

FONT_REG = "C:/Windows/Fonts/segoeui.ttf"
FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
FONT_SEMI = "C:/Windows/Fonts/segoeuisl.ttf"


def font(size, bold=False, semi=False):
    path = FONT_BOLD if bold else FONT_SEMI if semi else FONT_REG
    return ImageFont.truetype(path, size)


def wrap(draw, text, fnt, max_width):
    lines, current = [], ""
    for paragraph in text.split("\n"):
        for word in paragraph.split():
            trial = f"{current} {word}".strip()
            if draw.textlength(trial, font=fnt) <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
            current = ""
    return lines


def label(draw, xy, text, fnt, fill=NAVY, anchor="mm", max_width=None, spacing=4):
    if max_width is None:
        draw.text(xy, text, font=fnt, fill=fill, anchor=anchor)
        return
    lines = wrap(draw, text, fnt, max_width)
    total_h = len(lines) * (fnt.size + spacing)
    y = xy[1] - total_h / 2 + fnt.size / 2
    for line in lines:
        draw.text((xy[0], y), line, font=fnt, fill=fill, anchor=anchor)
        y += fnt.size + spacing


def box(draw, coords, title, sub=None, outline=BLUE, fill=WHITE, title_size=22, sub_size=19):
    x1, y1, x2, y2 = coords
    draw.rounded_rectangle(coords, radius=14, fill=fill, outline=outline, width=2)
    draw.text(((x1 + x2) / 2, y1 + (y2 - y1) * 0.33), title, font=font(title_size, bold=True), fill=NAVY, anchor="mm")
    if sub:
        label(
            draw,
            ((x1 + x2) / 2, y1 + (y2 - y1) * 0.70),
            sub,
            font(sub_size),
            fill=SLATE,
            max_width=(x2 - x1) - 18,
            spacing=2,
        )
    return coords


def arrow(draw, start, end, color=BLUE, width=3, head=9):
    draw.line([start, end], fill=color, width=width)
    import math

    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    p1 = (
        end[0] - head * math.cos(angle) + head * 0.55 * math.sin(angle),
        end[1] - head * math.sin(angle) - head * 0.55 * math.cos(angle),
    )
    p2 = (
        end[0] - head * math.cos(angle) - head * 0.55 * math.sin(angle),
        end[1] - head * math.sin(angle) + head * 0.55 * math.cos(angle),
    )
    draw.polygon([end, p1, p2], fill=color)


def canvas(title, subtitle, w=1400, h=800):
    img = Image.new("RGB", (w, h), CANVAS)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, w, 78], fill=NAVY)
    draw.text((34, 17), title, font=font(30, bold=True), fill=WHITE)
    draw.text((34, 54), subtitle, font=font(17), fill="#A6B6CB")
    draw.rectangle([0, 78, w, 82], fill=BLUE)
    return img, draw


def architecture():
    img, d = canvas(
        "Voltiq system architecture",
        "One Django backend serving two separate interfaces, one database and one service layer",
    )
    d.text((30, 90), "CLIENT LAYER", font=font(16, bold=True), fill=MUTED)
    d.text((430, 90), "DJANGO APPLICATION", font=font(16, bold=True), fill=MUTED)
    d.text((990, 90), "DATA & EXTERNAL SERVICES", font=font(16, bold=True), fill=MUTED)

    for coords, title, sub in [
        ((50, 145, 370, 235), "Storefront", "HTML, CSS, vanilla JS\nsearch, cart, checkout"),
        ((50, 260, 370, 350), "Customer account", "orders, addresses,\nwishlist, notifications"),
        ((50, 375, 370, 465), "Staff dashboard", "KPIs, catalogue,\norders, inventory"),
    ]:
        box(d, coords, title, sub, BLUE, BLUE_SOFT)

    d.rounded_rectangle((422, 115, 958, 700), radius=22, outline=NAVY, width=3)
    d.text((690, 142), "Django 5.2 + DRF", font=font(25, bold=True), fill=NAVY, anchor="mm")
    d.text((690, 166), "routing, permissions, forms, templates, services", font=font(16), fill=MUTED, anchor="mm")

    rows = [
        ("URLs & middleware", "sessions, CSRF, security headers"),
        ("Views, forms & DRF", "storefront, checkout, account, dashboard"),
        ("Services & signals", "orders, stock, payments, cache, cleanup"),
        ("ORM & business rules", "transactions, row locks, constraints"),
        ("Templates & assets", "HTML, modular CSS, vanilla JS, Chart.js"),
    ]
    y = 190
    for title, sub in rows:
        d.rounded_rectangle((455, y, 925, y + 72), radius=10, fill="#F8FAFC", outline="#DCE5F2", width=1)
        d.text((472, y + 21), title, font=font(22, bold=True), fill=BLUE)
        d.text((472, y + 49), sub, font=font(19), fill=SLATE)
        y += 94

    for coords, title, sub in [
        ((990, 145, 1370, 225), "PostgreSQL / SQLite", "primary relational database"),
        ((990, 245, 1370, 325), "Media & static", "images, avatars, WhiteNoise"),
        ((990, 345, 1370, 425), "Cache", "navigation, settings, home data"),
        ((990, 445, 1370, 525), "SMTP", "verification, reset, order email"),
        ((990, 545, 1370, 625), "eSewa / Khalti", "server-side initiation and verification"),
    ]:
        box(d, coords, title, sub, GREEN if coords[1] < 345 else AMBER, GREEN_SOFT if coords[1] < 345 else AMBER_SOFT, 21, 19)

    for y in (190, 305, 420):
        arrow(d, (372, y), (410, y), BLUE)
    for y in (185, 285, 385, 485, 585):
        arrow(d, (960, y), (980, y), SLATE, 2, 7)
    d.text((690, 716), "Application server", font=font(18, semi=True), fill=NAVY, anchor="mm")
    d.text(
        (690, 756),
        "ReportLab invoices run inside Django. Chart.js renders dashboard analytics in the browser.",
        font=font(18),
        fill=SLATE,
        anchor="mm",
    )
    img.save(OUT / "architecture.png")


def order_lifecycle():
    img, d = canvas(
        "Order and payment lifecycle",
        "From cart validation to delivery, with cancellation, refund and payment paths",
    )
    steps = [
        ("Cart", "stock-aware items\ncoupon and delivery"),
        ("Checkout", "contact, address,\ndelivery, review, pay"),
        ("Order created", "pending / unpaid\nstock deducted"),
        ("Confirmed", "payment verified\nor COD accepted"),
        ("Processing", "picking and packing"),
        ("Shipped", "courier, tracking\nout for delivery"),
        ("Delivered", "COD marked paid"),
    ]
    x = 30
    for index, (title, sub) in enumerate(steps):
        fill = GREEN_SOFT if title in {"Confirmed", "Delivered"} else BLUE_SOFT
        outline = GREEN if title in {"Confirmed", "Delivered"} else BLUE
        box(d, (x, 135, x + 170, 295), title, sub, outline, fill, 21, 19)
        if index < len(steps) - 1:
            arrow(d, (x + 172, 215), (x + 188, 215), BLUE if index < 4 else GREEN, 2, 8)
        x += 188

    d.rounded_rectangle((380, 345, 1020, 455), radius=14, fill=RED_SOFT, outline=RED, width=2)
    d.text((700, 372), "Cancellation / refund branch", font=font(22, bold=True), fill=RED, anchor="mm")
    d.text(
        (700, 400),
        "Allowed while pending, confirmed or processing. Stock is restored,",
        font=font(17),
        fill=SLATE,
        anchor="mm",
    )
    d.text(
        (700, 424),
        "paid orders are marked refunded, pending gateway attempts are cancelled.",
        font=font(17),
        fill=SLATE,
        anchor="mm",
    )
    d.text(
        (700, 448),
        "Every transition is written to status history.",
        font=font(17),
        fill=SLATE,
        anchor="mm",
    )
    arrow(d, (700, 297), (700, 340), RED, 2, 8)

    d.text((30, 500), "PAYMENT PATHS", font=font(18, bold=True), fill=MUTED)
    paths = [
        ("eSewa / Khalti", "redirect, callback, server verification"),
        ("Cash on delivery", "staff mark cash collected on delivery"),
        ("Bank transfer", "customer deposits, staff verify"),
        ("Payment audit", "attempts, payloads, status history"),
    ]
    x = 30
    for index, (title, sub) in enumerate(paths):
        color = [AMBER, GREEN, BLUE, MUTED][index]
        soft = [AMBER_SOFT, GREEN_SOFT, BLUE_SOFT, "#F1F5F9"][index]
        box(d, (x, 535, x + 310, 655), title, sub, color, soft, 22, 19)
        x += 330

    d.text((30, 700), "Status history", font=font(18, bold=True), fill=MUTED)
    d.text(
        (30, 730),
        "Every transition creates an OrderStatusHistory row with the staff member, timestamp and optional note.",
        font=font(18),
        fill=SLATE,
    )
    d.text(
        (30, 756),
        "Customers see the same timeline in their account. Failed or cancelled gateway attempts leave the order payable.",
        font=font(18),
        fill=SLATE,
    )
    img.save(OUT / "order-lifecycle.png")


def payment_verification():
    img, d = canvas(
        "Online payment verification",
        "No order is marked paid until the server verifies the gateway response and exact amount",
    )
    steps = [
        ("1. Start", "Payment row created\nwith a unique reference"),
        ("2. Gateway", "eSewa form or Khalti\nserver-side initiation"),
        ("3. Callback", "Browser returns with\na signed payload or pidx"),
        ("4. Verify", "Signature, status,\nreference and amount"),
        ("5. Record", "Order paid exactly once\nby database constraint"),
    ]
    x = 30
    for index, (title, sub) in enumerate(steps):
        outline = BLUE if index < 3 else GREEN
        fill = BLUE_SOFT if index < 3 else GREEN_SOFT
        box(d, (x, 125, x + 240, 265), title, sub, outline, fill, 22, 19)
        if index < 4:
            arrow(d, (x + 242, 195), (x + 278, 195), BLUE if index < 3 else GREEN, 2, 8)
        x += 278

    panels = [
        (
            30,
            "eSewa ePay v2",
            [
                "HMAC-SHA256 signature over signed fields",
                "Base64 callback payload decoded server-side",
                "Status API checks reference and total amount",
                "Order is marked paid only when all checks pass",
            ],
            AMBER,
            AMBER_SOFT,
        ),
        (
            490,
            "Khalti ePayment v2",
            [
                "Amount sent in paisa with purchase order ID",
                "Return URL carries order reference and pidx",
                "Lookup checks Completed, pidx and order ID",
                "Amount must equal order total x 100",
            ],
            BLUE,
            BLUE_SOFT,
        ),
        (
            950,
            "Defence in depth",
            [
                "Gateway secrets live only in environment variables",
                "One successful payment per order is enforced in SQL",
                "Duplicate callbacks are idempotent and return success",
                "Failed attempts stay logged and the order remains payable",
            ],
            GREEN,
            GREEN_SOFT,
        ),
    ]
    for x1, title, items, outline, fill in panels:
        x2 = x1 + 420
        d.rounded_rectangle((x1, 310, x2, 650), radius=14, fill=WHITE, outline=outline, width=2)
        d.rectangle([x1, 310, x2, 355], fill=fill)
        d.text((x1 + 18, 332), title, font=font(22, bold=True), fill=NAVY, anchor="lm")
        y = 388
        for item in items:
            d.ellipse((x1 + 18, y + 5, x1 + 28, y + 15), fill=outline)
            label(d, (x1 + 38, y + 10), item, font(18), fill=SLATE, anchor="lm", max_width=360, spacing=2)
            y += 62

    d.rounded_rectangle((30, 675, 1370, 735), radius=12, fill="#FFFBEB", outline=AMBER, width=2)
    d.text(
        (700, 705),
        "Development simulator: only when DEBUG=True and PAYMENT_SIMULATION=True. Labelled Sandbox; no real gateway is contacted.",
        font=font(18, semi=True),
        fill="#92400E",
        anchor="mm",
    )
    img.save(OUT / "payment-verification.png")


def data_model():
    img, d = canvas(
        "Core data model",
        "Normalised entities, audit trails and clear ownership boundaries - full field lists are in Appendix A",
        h=900,
    )
    groups = [
        (20, "CATALOGUE", BLUE, BLUE_SOFT),
        (470, "CUSTOMER & SHOPPING", GREEN, GREEN_SOFT),
        (930, "COMMERCE & PAYMENTS", AMBER, AMBER_SOFT),
    ]
    for x, title, outline, fill in groups:
        width = 420 if x < 930 else 450
        d.rounded_rectangle((x, 100, x + width, 700), radius=20, fill=WHITE, outline=outline, width=2)
        d.rectangle([x, 100, x + width, 142], fill=fill)
        d.text((x + 18, 121), title, font=font(19, bold=True), fill=NAVY, anchor="lm")

    def entity(x, y, title, sub, outline=BLUE, w=185, h=74, title_size=21, sub_size=18):
        d.rounded_rectangle((x, y, x + w, y + h), radius=10, fill="#F8FAFC", outline="#DCE5F2", width=1)
        d.rectangle([x, y, x + w, y + 38], fill=outline)
        d.text((x + 10, y + 19), title, font=font(title_size, bold=True), fill=WHITE, anchor="lm")
        if sub:
            d.text((x + 10, y + 56), sub, font=font(sub_size), fill=SLATE, anchor="lm")
        return (x, y, x + w, y + h)

    # Catalogue
    entity(45, 165, "Category", "name, slug, parent")
    entity(240, 165, "Product", "price, stock, facets")
    entity(45, 260, "Brand", "name, logo")
    entity(240, 260, "SpecField", "category, key, type")
    entity(45, 355, "ProductImage", "product, primary")
    entity(240, 355, "SpecValue", "product, value")
    entity(45, 450, "StockHistory", "change, reason, order", GREEN)

    # Customer
    entity(495, 165, "User", "email, role, verified", GREEN)
    entity(690, 165, "Address", "province, default", GREEN)
    entity(495, 260, "Cart", "user or session", GREEN)
    entity(690, 260, "Wishlist", "user (one-to-one)", GREEN)
    entity(495, 355, "CartItem", "cart, product, qty", GREEN)
    entity(690, 355, "WishlistItem", "wishlist, product", GREEN)
    entity(495, 450, "Notification", "user, kind, read", GREEN)
    entity(690, 450, "Review", "rating, verified", GREEN)

    # Commerce
    entity(955, 165, "Order", "number, totals", AMBER, 200)
    entity(1165, 165, "OrderItem", "price snapshot", AMBER, 200)
    entity(955, 260, "Payment", "amount, status", AMBER, 200)
    entity(1165, 260, "PaymentTxn", "event, payload, IP", AMBER, 200)
    entity(955, 355, "Coupon", "code, value, limits", AMBER, 200)
    entity(1165, 355, "StatusHistory", "status, note, staff", AMBER, 200)

    # Connections
    arrow(d, (230, 202), (238, 202), BLUE, 2, 6)
    arrow(d, (230, 297), (238, 240), BLUE, 2, 6)
    arrow(d, (140, 240), (140, 353), BLUE, 2, 6)
    arrow(d, (330, 340), (330, 353), BLUE, 2, 6)
    arrow(d, (140, 430), (140, 448), BLUE, 2, 6)
    arrow(d, (680, 202), (688, 202), GREEN, 2, 6)
    arrow(d, (590, 240), (590, 258), GREEN, 2, 6)
    arrow(d, (590, 335), (590, 353), GREEN, 2, 6)
    arrow(d, (785, 335), (785, 353), GREEN, 2, 6)
    arrow(d, (1155, 202), (1163, 202), AMBER, 2, 6)
    arrow(d, (1055, 240), (1055, 258), AMBER, 2, 6)
    arrow(d, (1265, 240), (1265, 258), AMBER, 2, 6)
    arrow(d, (1055, 335), (1055, 353), AMBER, 2, 6)

    d.rounded_rectangle((20, 735, 1380, 845), radius=14, fill=WHITE, outline="#D7E2F2", width=1)
    d.text((40, 760), "Key constraints", font=font(19, bold=True), fill=NAVY)
    d.text(
        (40, 790),
        "Unique email, SKU and slug  |  one cart item per product  |  one review per customer/product  |  one successful payment per order",
        font=font(18),
        fill=SLATE,
    )
    d.text(
        (40, 816),
        "Stock and status changes are append-only audit rows. Order items keep name, SKU, image and price snapshots.",
        font=font(18),
        fill=SLATE,
    )
    img.save(OUT / "data-model.png")


if __name__ == "__main__":
    architecture()
    order_lifecycle()
    payment_verification()
    data_model()
    print("Diagrams written to", OUT)
