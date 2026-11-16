"""Shared helpers for the Voltiq test suite.

Not a test module itself (Django only discovers ``test*.py``), so importing
these factories keeps the individual test files short and consistent.
"""
import uuid
from decimal import Decimal

from django.utils import timezone

from apps.accounts.models import Address, User
from apps.categories.models import Brand, Category
from apps.orders.models import Order, OrderItem, ShippingMethod
from apps.products.models import Product

DEFAULT_PASSWORD = "VoltiqTest!2026"


def make_user(email=None, password=DEFAULT_PASSWORD, verified=True, **kwargs):
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    user = User.objects.create_user(email=email, password=password, **kwargs)
    if verified:
        user.is_email_verified = True
        user.email_verified_at = timezone.now()
        user.save(update_fields=["is_email_verified", "email_verified_at"])
    return user


def make_staff(email=None, admin=False, **kwargs):
    email = email or f"staff-{uuid.uuid4().hex[:8]}@example.com"
    return make_user(
        email=email,
        role=User.Role.ADMIN if admin else User.Role.STAFF,
        is_staff=True,
        is_superuser=admin,
        **kwargs,
    )


def make_category(name=None, **kwargs):
    name = name or f"Category {uuid.uuid4().hex[:6]}"
    return Category.objects.create(name=name, **kwargs)


def make_brand(name=None, **kwargs):
    name = name or f"Brand {uuid.uuid4().hex[:6]}"
    return Brand.objects.create(name=name, **kwargs)


def make_product(sku=None, price=Decimal("1000.00"), stock=10, category=None, brand=None, **kwargs):
    sku = sku or f"SKU-{uuid.uuid4().hex[:8].upper()}"
    category = category or make_category()
    brand = brand or make_brand()
    defaults = {
        "name": f"Test product {sku}",
        "description": "A reliable test product used by the Voltiq test suite.",
        "price": price,
        "stock_quantity": stock,
    }
    defaults.update(kwargs)
    return Product.objects.create(sku=sku, category=category, brand=brand, **defaults)


def make_shipping(code=None, charge=Decimal("0.00"), **kwargs):
    code = code or f"ship-{uuid.uuid4().hex[:8]}"
    defaults = {
        "name": "Test delivery",
        "charge": charge,
        "min_days": 1,
        "max_days": 3,
        "is_active": True,
    }
    defaults.update(kwargs)
    return ShippingMethod.objects.create(code=code, **defaults)


def make_address(user, **kwargs):
    defaults = {
        "label": "Home",
        "full_name": user.get_full_name(),
        "phone": "+977 980-000-0000",
        "street_address": "House 1, Test Street",
        "city": "Kathmandu",
        "district": "Kathmandu",
        "province": "bagmati",
        "postal_code": "44600",
        "country": "Nepal",
        "is_default": True,
    }
    defaults.update(kwargs)
    return Address.objects.create(user=user, **defaults)


def make_order(
    *,
    user,
    product,
    quantity=1,
    status=Order.Status.PENDING,
    payment_status=Order.PaymentStatus.PENDING,
    payment_method=Order.PaymentMethod.COD,
    shipping_method=None,
    **kwargs,
):
    shipping_method = shipping_method or make_shipping()
    unit_price = product.current_price
    subtotal = unit_price * quantity
    fee = shipping_method.fee_for(subtotal)
    order = Order.objects.create(
        user=user,
        email=user.email,
        phone="+977 980-000-0000",
        full_name=user.get_full_name(),
        shipping_full_name=user.get_full_name(),
        shipping_phone="+977 980-000-0000",
        shipping_street="House 1, Test Street",
        shipping_city="Kathmandu",
        shipping_district="Kathmandu",
        shipping_province="bagmati",
        shipping_postal_code="44600",
        shipping_country="Nepal",
        shipping_method=shipping_method,
        shipping_method_name=shipping_method.name,
        shipping_fee=fee,
        subtotal=subtotal,
        total=subtotal + fee,
        status=status,
        payment_status=payment_status,
        payment_method=payment_method,
        **kwargs,
    )
    OrderItem.objects.create(
        order=order,
        product=product,
        product_name=product.name,
        sku=product.sku,
        unit_price=unit_price,
        quantity=quantity,
    )
    return order
