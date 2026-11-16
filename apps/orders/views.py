import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from apps.accounts.forms import AddressForm
from apps.accounts.models import Address
from apps.cart.services import add_to_cart, apply_coupon, get_cart, remove_coupon
from apps.cart.services import CartError
from apps.core.templatetags.voltiq import npr
from apps.orders.forms import (
    CheckoutContactForm,
    CouponCodeForm,
    PaymentMethodForm,
    ShippingMethodForm,
)
from apps.orders.models import Order, ShippingMethod
from apps.orders.services import CheckoutError, cancel_order, create_order_from_cart
from apps.payments.gateways.base import PaymentGatewayError
from apps.payments.services import available_payment_methods, start_payment

logger = logging.getLogger("apps.orders")
SESSION_KEY = "checkout"


def _checkout_state(request):
    return request.session.get(SESSION_KEY, {})


def _save_state(request, **updates):
    state = _checkout_state(request)
    state.update(updates)
    request.session[SESSION_KEY] = state
    request.session.modified = True
    return state


def _active_cart(request):
    cart = get_cart(request, create=False)
    if not cart or not cart.items.exists():
        return None
    return cart


def _require_verified(request):
    if not request.user.is_email_verified:
        messages.warning(
            request,
            "Please verify your email address before checkout. We sent you a verification link.",
        )
        return redirect("accounts:verify_pending")
    return None


def checkout_contact(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('accounts:login')}?next={request.get_full_path()}")
    cart = _active_cart(request)
    if not cart:
        messages.info(request, "Your cart is empty. Add a product before checking out.")
        return redirect("cart:detail")
    gate = _require_verified(request)
    if gate:
        return gate

    state = _checkout_state(request)
    initial = state.get(
        "contact",
        {
            "full_name": request.user.get_full_name(),
            "email": request.user.email,
            "phone": request.user.phone,
        },
    )
    form = CheckoutContactForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        _save_state(request, contact=form.cleaned_data, reviewed=False)
        return redirect("checkout:address")
    return render(
        request,
        "checkout/contact.html",
        {"form": form, "cart": cart, "step": 1, "state": state},
    )


@login_required
def checkout_address(request):
    cart = _active_cart(request)
    if not cart:
        return redirect("cart:detail")
    gate = _require_verified(request)
    if gate:
        return gate
    state = _checkout_state(request)
    if not state.get("contact"):
        messages.info(request, "Start by confirming your contact details.")
        return redirect("checkout:contact")

    addresses = request.user.addresses.all()
    new_address_form = AddressForm(user=request.user)

    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "existing":
            address = Address.objects.filter(
                pk=request.POST.get("address_id"), user=request.user
            ).first()
            if not address:
                messages.error(request, "Please select a valid delivery address.")
            else:
                _save_state(request, address_id=address.pk, reviewed=False)
                return redirect("checkout:shipping")
        elif form_type == "new":
            new_address_form = AddressForm(request.POST, user=request.user)
            if new_address_form.is_valid():
                address = new_address_form.save()
                _save_state(request, address_id=address.pk, reviewed=False)
                messages.success(request, "New delivery address saved.")
                return redirect("checkout:shipping")
            messages.error(request, "Please correct the address details below.")

    selected_id = state.get("address_id")
    if not selected_id and addresses.exists():
        selected_id = addresses.first().pk
    return render(
        request,
        "checkout/address.html",
        {
            "cart": cart,
            "addresses": addresses,
            "new_address_form": new_address_form,
            "selected_id": selected_id,
            "step": 2,
            "state": state,
        },
    )


@login_required
def checkout_shipping(request):
    cart = _active_cart(request)
    if not cart:
        return redirect("cart:detail")
    state = _checkout_state(request)
    if not state.get("address_id"):
        messages.info(request, "Choose a delivery address first.")
        return redirect("checkout:address")
    address = Address.objects.filter(pk=state["address_id"], user=request.user).first()
    if not address:
        return redirect("checkout:address")

    methods = ShippingMethod.objects.filter(is_active=True)
    initial_method = state.get("shipping_method_id")
    if not initial_method:
        default = methods.filter(code="standard").first() or methods.first()
        initial_method = default.pk if default else None
    form = ShippingMethodForm(
        request.POST or None,
        initial={"shipping_method": initial_method},
    )
    form.fields["shipping_method"].queryset = methods

    if request.method == "POST" and form.is_valid():
        method = form.cleaned_data["shipping_method"]
        _save_state(request, shipping_method_id=method.pk, reviewed=False)
        cart.shipping_method = method
        cart.save(update_fields=["shipping_method", "updated_at"])
        return redirect("checkout:review")

    return render(
        request,
        "checkout/shipping.html",
        {"cart": cart, "address": address, "form": form, "methods": methods, "step": 3, "state": state},
    )


@login_required
def checkout_review(request):
    cart = _active_cart(request)
    if not cart:
        return redirect("cart:detail")
    state = _checkout_state(request)
    address = Address.objects.filter(pk=state.get("address_id"), user=request.user).first()
    method = ShippingMethod.objects.filter(pk=state.get("shipping_method_id")).first()
    if not address or not method:
        messages.info(request, "Complete the delivery steps first.")
        return redirect("checkout:address")

    cart.shipping_method = method
    cart.save(update_fields=["shipping_method", "updated_at"])
    coupon_form = CouponCodeForm(request.POST or None)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "apply_coupon" and coupon_form.is_valid():
            try:
                coupon = apply_coupon(request, coupon_form.cleaned_data["code"])
                messages.success(request, f"Coupon {coupon.code} applied.")
            except CartError as exc:
                messages.error(request, str(exc))
            return redirect("checkout:review")
        if action == "remove_coupon":
            remove_coupon(request)
            messages.success(request, "Coupon removed.")
            return redirect("checkout:review")

    conflicts = cart.has_stock_conflicts()
    _save_state(request, reviewed=True)
    return render(
        request,
        "checkout/review.html",
        {
            "cart": cart,
            "items": cart.items.select_related("product").prefetch_related("product__images"),
            "address": address,
            "shipping_method": method,
            "coupon_form": coupon_form,
            "conflicts": conflicts,
            "step": 4,
            "state": state,
        },
    )


@login_required
def checkout_payment(request):
    cart = _active_cart(request)
    if not cart:
        return redirect("cart:detail")
    state = _checkout_state(request)
    address = Address.objects.filter(pk=state.get("address_id"), user=request.user).first()
    method = ShippingMethod.objects.filter(pk=state.get("shipping_method_id")).first()
    if not address or not method or not state.get("contact"):
        messages.info(request, "Complete the earlier checkout steps first.")
        return redirect("checkout:address")
    if not state.get("reviewed"):
        return redirect("checkout:review")
    if cart.has_stock_conflicts():
        messages.error(request, "Some items no longer have enough stock. Please review your cart.")
        return redirect("cart:detail")

    cart.shipping_method = method
    cart.save(update_fields=["shipping_method", "updated_at"])
    methods = available_payment_methods()
    form = PaymentMethodForm(request.POST or None, methods=methods)

    if request.method == "POST" and form.is_valid():
        gateway_code = form.cleaned_data["payment_method"]
        try:
            order = create_order_from_cart(
                cart,
                user=request.user,
                contact=state["contact"],
                shipping_address=address,
                shipping_method=method,
                payment_method=gateway_code,
                customer_notes=form.cleaned_data.get("customer_notes", ""),
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except CheckoutError as exc:
            messages.error(request, str(exc))
            return redirect("cart:detail")
        except Exception:
            logger.exception("Order placement failed")
            messages.error(request, "We could not place your order. Please try again.")
            return redirect("cart:detail")

        request.session.pop(SESSION_KEY, None)
        request.session.modified = True
        try:
            payment, initiation = start_payment(order, gateway_code, request)
        except PaymentGatewayError as exc:
            messages.warning(
                request,
                f"Order {order.order_number} was created but the payment could not start: {exc}",
            )
            return redirect("orders:detail", order_number=order.order_number)

        if gateway_code == "cod":
            messages.success(request, "Order placed! Pay cash when your order arrives.")
        elif gateway_code == "bank":
            messages.info(request, "Complete the bank transfer using the reference provided.")
        else:
            messages.info(request, "Order created. Redirecting to the payment gateway…")
        if initiation.form_fields:
            return render(
                request,
                "payments/redirect.html",
                {
                    "form_url": initiation.form_url,
                    "form_fields": initiation.form_fields,
                    "order": order,
                    "message": initiation.message,
                },
            )
        return HttpResponseRedirect(initiation.redirect_url)

    return render(
        request,
        "checkout/payment.html",
        {
            "cart": cart,
            "items": cart.items.select_related("product").prefetch_related("product__images"),
            "address": address,
            "shipping_method": method,
            "form": form,
            "methods": methods,
            "step": 5,
            "state": state,
        },
    )


def confirmation(request, order_number):
    order = get_object_or_404(
        Order.objects.select_related("shipping_method").prefetch_related("items", "payments"), order_number=order_number
    )
    if not request.user.is_authenticated:
        messages.info(request, "Sign in to view this order confirmation.")
        return redirect(f"{reverse('accounts:login')}?next={request.get_full_path()}")
    if order.user_id != request.user.id and not request.user.is_staff:
        return redirect("core:home")
    return render(request, "orders/confirmation.html", {"order": order, "step": 6})


@login_required
def order_list(request):
    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related("items")
        .select_related("shipping_method")
        .order_by("-created_at")
    )
    status = request.GET.get("status", "")
    if status in dict(Order.Status.choices):
        orders = orders.filter(status=status)
    paginator = Paginator(orders, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "orders/list.html",
        {"page_obj": page_obj, "orders": page_obj.object_list, "status": status},
    )


def _get_order_for_user(request, order_number):
    order = get_object_or_404(
        Order.objects.select_related("shipping_method", "coupon")
        .prefetch_related("items__product", "payments__transactions", "status_history", "coupon_usages"),
        order_number=order_number,
    )
    if order.user_id != request.user.id and not request.user.is_staff:
        return None
    return order


@login_required
def order_detail(request, order_number):
    order = _get_order_for_user(request, order_number)
    if not order:
        messages.error(request, "We couldn't find that order in your account.")
        return redirect("orders:list")
    methods = available_payment_methods()
    return render(request, "orders/detail.html", {"order": order, "payment_methods": methods})


@login_required
def order_track(request, order_number):
    order = _get_order_for_user(request, order_number)
    if not order:
        return redirect("orders:list")
    return render(request, "orders/track.html", {"order": order})


@login_required
@require_POST
def order_cancel(request, order_number):
    order = _get_order_for_user(request, order_number)
    if not order:
        return redirect("orders:list")
    try:
        cancel_order(order, changed_by=request.user, reason=request.POST.get("reason", "Cancelled by customer"))
        messages.success(request, f"Order {order.order_number} has been cancelled and stock restored.")
    except CheckoutError as exc:
        messages.error(request, str(exc))
    return redirect("orders:detail", order_number=order.order_number)


@login_required
@require_POST
def order_reorder(request, order_number):
    order = _get_order_for_user(request, order_number)
    if not order:
        return redirect("orders:list")
    added, failed = 0, []
    for item in order.items.select_related("product"):
        if not item.product or not item.product.is_active:
            failed.append(item.product_name)
            continue
        try:
            add_to_cart(request, item.product, item.quantity)
            added += 1
        except CartError:
            failed.append(item.product_name)
    if added:
        messages.success(request, f"{added} item(s) added back to your cart.")
    if failed:
        messages.warning(request, "Some items are unavailable: " + ", ".join(failed))
    return redirect("cart:detail")


@login_required
def order_payment(request, order_number):
    order = _get_order_for_user(request, order_number)
    if not order:
        return redirect("orders:list")
    if not order.can_pay:
        messages.info(request, "This order does not require payment right now.")
        return redirect("orders:detail", order_number=order.order_number)
    methods = available_payment_methods()
    form = PaymentMethodForm(request.POST or None, methods=methods, initial={"payment_method": "esewa"})
    if request.method == "POST" and form.is_valid():
        try:
            payment, initiation = start_payment(order, form.cleaned_data["payment_method"], request)
        except PaymentGatewayError as exc:
            messages.error(request, str(exc))
            return redirect("orders:payment", order_number=order.order_number)
        if initiation.form_fields:
            return render(
                request,
                "payments/redirect.html",
                {
                    "form_url": initiation.form_url,
                    "form_fields": initiation.form_fields,
                    "order": order,
                    "message": initiation.message,
                },
            )
        return HttpResponseRedirect(initiation.redirect_url)
    return render(
        request,
        "orders/payment.html",
        {"order": order, "form": form, "methods": methods},
    )


@login_required
def invoice_pdf(request, order_number):
    order = _get_order_for_user(request, order_number)
    if not order:
        return redirect("orders:list")
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="invoice-{order.order_number}.pdf"'

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    navy = colors.HexColor("#0B1220")
    accent = colors.HexColor("#2563EB")
    muted = colors.HexColor("#64748B")
    y = height - 22 * mm

    pdf.setFillColor(navy)
    pdf.rect(0, height - 34 * mm, width, 34 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(20 * mm, height - 20 * mm, "VOLTIQ")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(20 * mm, height - 26 * mm, "Premium electronics • Kathmandu, Nepal")
    pdf.drawRightString(width - 20 * mm, height - 20 * mm, "TAX INVOICE")
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawRightString(width - 20 * mm, height - 27 * mm, order.order_number)

    y = height - 44 * mm
    pdf.setFillColor(navy)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(20 * mm, y, "BILLED TO")
    pdf.drawString(110 * mm, y, "ORDER DETAILS")
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(colors.HexColor("#334155"))
    billed_lines = [
        order.full_name,
        order.shipping_street,
        f"{order.shipping_city}, {order.shipping_district}",
        order.shipping_province.title(),
        order.email,
        order.phone,
    ]
    details_lines = [
        f"Placed: {timezone.localtime(order.created_at):%d %b %Y, %I:%M %p}",
        f"Status: {order.get_status_display()}",
        f"Payment: {order.get_payment_method_display()} ({order.get_payment_status_display()})",
        f"Delivery: {order.shipping_method_name or 'Standard'}",
    ]
    for i, line in enumerate(billed_lines):
        pdf.drawString(20 * mm, y - 6 * mm - i * 5 * mm, line[:70])
    for i, line in enumerate(details_lines):
        pdf.drawString(110 * mm, y - 6 * mm - i * 5 * mm, line[:70])

    y -= 48 * mm
    pdf.setFillColor(navy)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(20 * mm, y, "ITEM")
    pdf.drawRightString(120 * mm, y, "QTY")
    pdf.drawRightString(150 * mm, y, "UNIT PRICE")
    pdf.drawRightString(width - 20 * mm, y, "TOTAL")
    pdf.setStrokeColor(colors.HexColor("#CBD5E1"))
    pdf.line(20 * mm, y - 2 * mm, width - 20 * mm, y - 2 * mm)
    y -= 8 * mm
    pdf.setFont("Helvetica", 9)
    for item in order.items.all():
        pdf.setFillColor(colors.HexColor("#0F172A"))
        pdf.drawString(20 * mm, y, item.product_name[:58])
        pdf.drawRightString(120 * mm, y, str(item.quantity))
        pdf.drawRightString(150 * mm, y, f"Rs. {item.unit_price:,.2f}")
        pdf.drawRightString(width - 20 * mm, y, f"Rs. {item.line_total:,.2f}")
        pdf.setFillColor(muted)
        pdf.setFont("Helvetica", 7.5)
        pdf.drawString(20 * mm, y - 4 * mm, f"SKU: {item.sku}")
        pdf.setFont("Helvetica", 9)
        y -= 12 * mm
        if y < 60 * mm:
            pdf.showPage()
            y = height - 25 * mm

    y -= 4 * mm
    pdf.line(110 * mm, y, width - 20 * mm, y)
    y -= 7 * mm
    rows = [
        ("Subtotal", order.subtotal),
        ("Discount", -order.discount_amount),
        ("Delivery", order.shipping_fee),
        ("Total", order.total),
    ]
    for label, value in rows:
        pdf.setFont("Helvetica-Bold" if label == "Total" else "Helvetica", 10 if label == "Total" else 9)
        pdf.setFillColor(navy if label == "Total" else colors.HexColor("#334155"))
        pdf.drawString(110 * mm, y, label)
        pdf.drawRightString(width - 20 * mm, y, f"Rs. {value:,.2f}")
        y -= 6 * mm

    pdf.setFillColor(muted)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(20 * mm, 20 * mm, "Thank you for shopping with Voltiq. support@voltiq.com.np • +977 980-000-0000")
    pdf.drawRightString(width - 20 * mm, 20 * mm, "This is a computer-generated invoice.")
    pdf.showPage()
    pdf.save()
    return response
