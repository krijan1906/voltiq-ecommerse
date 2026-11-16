"""Transactional order placement, cancellation and customer communication."""
import logging
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.template.loader import render_to_string
from django.utils import timezone

from apps.accounts.models import Notification
from apps.cart.models import Cart
from apps.inventory.models import StockHistory
from apps.inventory.services import StockError, adjust_stock
from apps.orders.models import Coupon, CouponUsage, Order, OrderItem, OrderStatusHistory
from apps.products.models import Product

logger = logging.getLogger("apps.orders")


class CheckoutError(Exception):
    pass


def send_order_confirmation(order):
    try:
        lines = "\n".join(
            f"  {item.quantity} × {item.product_name} — Rs. {item.line_total:,.2f}" for item in order.items.all()
        )
        message = (
            f"Hi {order.full_name},\n\n"
            f"Thank you for shopping with Voltiq. Your order {order.order_number} has been received.\n\n"
            f"{lines}\n\n"
            f"Subtotal: Rs. {order.subtotal:,.2f}\n"
            f"Discount: Rs. {order.discount_amount:,.2f}\n"
            f"Delivery: Rs. {order.shipping_fee:,.2f}\n"
            f"Total: Rs. {order.total:,.2f}\n\n"
            f"Payment method: {order.get_payment_method_display()}\n"
            f"Delivery to: {order.shipping_full_name}, {order.shipping_street}, "
            f"{order.shipping_city}, {order.shipping_district}\n\n"
            f"Track your order: {settings.SITE_URL}{order.get_absolute_url()}\n\n"
            f"Need help? Reply to this email or call {settings.SUPPORT_EMAIL}.\n\n"
            f"— Team Voltiq"
        )
        send_mail(
            f"Order confirmed — {order.order_number}",
            message,
            settings.DEFAULT_FROM_EMAIL,
            [order.email],
            fail_silently=True,
        )
    except Exception:  # pragma: no cover - email failure must never break checkout
        logger.exception("Unable to send order confirmation for %s", order.order_number)


@transaction.atomic
def create_order_from_cart(
    cart,
    *,
    user,
    contact,
    shipping_address,
    shipping_method,
    payment_method,
    customer_notes="",
    ip_address=None,
    user_agent="",
):
    """Validate inventory, snapshot prices and create an order atomically."""
    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    items = list(cart.items.select_related("product").order_by("id"))
    if not items:
        raise CheckoutError("Your cart is empty.")

    product_ids = [item.product_id for item in items]
    locked = {
        product.pk: product
        for product in Product.objects.select_for_update().select_related("category").filter(pk__in=product_ids)
    }

    subtotal = Decimal("0")
    for item in items:
        product = locked.get(item.product_id)
        if not product or not product.is_active or not product.category.is_active:
            raise CheckoutError(f"{item.product.name} is no longer available. Please remove it from your cart.")
        if item.quantity > product.stock_quantity:
            raise CheckoutError(
                f"Only {product.stock_quantity} unit(s) of {product.name} remain in stock. "
                "Please update your cart."
            )
        subtotal += product.current_price * item.quantity

    coupon = None
    discount = Decimal("0")
    if cart.coupon_id:
        coupon = cart.coupon.__class__.objects.select_for_update().get(pk=cart.coupon_id)
        valid, reason = coupon.validate_for(subtotal, user)
        if not valid:
            raise CheckoutError(f"Coupon issue: {reason}. Please remove the coupon and try again.")
        discount = coupon.calculate_discount(subtotal)

    shipping_fee = shipping_method.fee_for(subtotal)
    total = max(Decimal("0"), subtotal - discount + shipping_fee)

    order = Order.objects.create(
        user=user if user and user.is_authenticated else None,
        email=contact["email"],
        phone=contact["phone"],
        full_name=contact["full_name"],
        shipping_full_name=shipping_address.full_name,
        shipping_phone=shipping_address.phone,
        shipping_street=shipping_address.street_address,
        shipping_city=shipping_address.city,
        shipping_district=shipping_address.district,
        shipping_province=shipping_address.province,
        shipping_postal_code=shipping_address.postal_code,
        shipping_country=shipping_address.country,
        shipping_method=shipping_method,
        shipping_method_name=shipping_method.name,
        shipping_fee=shipping_fee,
        subtotal=subtotal,
        coupon=coupon,
        coupon_code=coupon.code if coupon else "",
        discount_amount=discount,
        total=total,
        payment_method=payment_method,
        customer_notes=customer_notes,
        ip_address=ip_address,
        user_agent=user_agent[:300],
    )

    order_items = []
    for item in items:
        product = locked[item.product_id]
        unit_price = product.current_price
        order_items.append(
            OrderItem(
                order=order,
                product=product,
                product_name=product.name,
                sku=product.sku,
                image_url=product.primary_image_url or "",
                unit_price=unit_price,
                quantity=item.quantity,
                line_total=unit_price * item.quantity,
            )
        )
    OrderItem.objects.bulk_create(order_items)

    # Deduct stock with row locks and a full audit trail.
    for item in items:
        product = locked[item.product_id]
        adjust_stock(
            product,
            -item.quantity,
            StockHistory.Reason.SALE,
            reference=order.order_number,
            order=order,
            user=user,
        )
        Product.objects.filter(pk=product.pk).update(sales_count=F("sales_count") + item.quantity)

    if coupon:
        CouponUsage.objects.create(coupon=coupon, user=user if user.is_authenticated else None, email=order.email, order=order)
        Coupon.objects.filter(pk=coupon.pk).update(used_count=F("used_count") + 1)
        order.coupon = coupon

    OrderStatusHistory.objects.create(
        order=order,
        status=Order.Status.PENDING,
        note="Order placed successfully.",
        changed_by=user if user and user.is_authenticated else None,
    )
    cart.items.all().delete()
    cart.coupon = None
    cart.save(update_fields=["coupon", "updated_at"])

    if order.user_id:
        Notification.push(
            order.user,
            "Order placed",
            f"Your order {order.order_number} has been placed. We'll keep you updated.",
            url=order.get_absolute_url(),
            kind=Notification.Kind.ORDER,
        )
    transaction.on_commit(lambda: send_order_confirmation(order))
    return order


@transaction.atomic
def cancel_order(order, changed_by=None, reason=""):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if not order.can_cancel:
        raise CheckoutError("This order can no longer be cancelled online. Please contact support.")
    from apps.inventory.services import restock_order

    restock_order(order, changed_by=changed_by, reason=StockHistory.Reason.CANCELLATION)
    was_paid = order.payment_status in {
        Order.PaymentStatus.PAID,
        Order.PaymentStatus.PARTIALLY_REFUNDED,
    }
    if was_paid:
        order.payment_status = Order.PaymentStatus.REFUNDED
        order.status = Order.Status.REFUNDED
        order.payments.filter(status="success").update(
            status="refunded", refunded_at=timezone.now(), is_verified=True
        )
    else:
        order.status = Order.Status.CANCELLED
        order.payments.filter(status__in=["initiated", "pending"]).update(
            status="cancelled", failed_reason="Order cancelled by customer", completed_at=timezone.now()
        )
    order.cancelled_at = timezone.now()
    order.save()
    OrderStatusHistory.objects.create(
        order=order,
        status=order.status,
        note=reason[:300] or "Order cancelled.",
        changed_by=changed_by if changed_by and changed_by.is_authenticated else None,
    )
    if order.user_id:
        Notification.push(
            order.user,
            "Order cancelled",
            f"Order {order.order_number} has been cancelled. "
            + ("A refund has been recorded." if was_paid else ""),
            url=order.get_absolute_url(),
            kind=Notification.Kind.ORDER,
        )
    return order


def order_items_for_user(user, product):
    return OrderItem.objects.filter(
        order__user=user,
        product=product,
    ).exclude(order__status__in=[Order.Status.CANCELLED, Order.Status.REFUNDED])


def order_paid_summary():
    from django.db.models import Sum

    return Order.objects.filter(payment_status=Order.PaymentStatus.PAID).aggregate(total=Sum("total"))["total"] or 0
