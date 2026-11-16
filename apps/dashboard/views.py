import csv
import json
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.forms import inlineformset_factory
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from apps.accounts.decorators import admin_required, staff_required
from apps.accounts.models import Address, Notification, User
from apps.categories.models import Brand, Category
from apps.core.forms import NewsletterForm
from apps.core.models import ContactMessage, NewsletterSubscription, SiteSetting
from apps.dashboard.forms import (
    BrandForm,
    CategoryForm,
    CouponForm,
    OrderStatusForm,
    ProductForm,
    ProductImageUploadForm,
    ShippingMethodForm,
    SiteSettingForm,
    SpecificationFieldForm,
    StockAdjustForm,
)
from apps.inventory.models import StockHistory
from apps.inventory.services import StockError, restock_order, set_stock
from apps.orders.models import Coupon, Order, OrderItem, ShippingMethod
from apps.orders.services import CheckoutError, cancel_order
from apps.payments.models import Payment
from apps.payments.services import mark_cod_collected, record_manual_refund
from apps.products.models import Product, ProductImage, ProductSpecification, SpecificationField
from apps.reviews.models import Review

ProductSpecificationFormSet = inlineformset_factory(
    Product,
    ProductSpecification,
    fields=("name", "value", "unit", "sort_order"),
    extra=6,
    can_delete=True,
)

PAGE_SIZE = 20


def _paginate(request, queryset, per_page=PAGE_SIZE):
    from django.core.paginator import Paginator

    paginator = Paginator(queryset, per_page)
    page = paginator.get_page(request.GET.get("page"))
    return page, page.object_list


def _revenue_series(days=30):
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    rows = (
        Order.objects.filter(
            payment_status=Order.PaymentStatus.PAID,
            created_at__date__gte=start,
            created_at__date__lte=today,
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(revenue=Sum("total"), orders=Count("id"))
        .order_by("day")
    )
    mapping = {row["day"]: row for row in rows}
    labels, revenue, orders = [], [], []
    for offset in range(days):
        day = start + timedelta(days=offset)
        row = mapping.get(day)
        labels.append(day.strftime("%d %b"))
        revenue.append(float(row["revenue"]) if row else 0)
        orders.append(row["orders"] if row else 0)
    return labels, revenue, orders


def _summary():
    paid = Order.objects.filter(payment_status=Order.PaymentStatus.PAID)
    today = timezone.localdate()
    month_start = today.replace(day=1)
    week_start = today - timedelta(days=6)
    return {
        "revenue_total": paid.aggregate(v=Sum("total"))["v"] or 0,
        "revenue_today": paid.filter(created_at__date=today).aggregate(v=Sum("total"))["v"] or 0,
        "revenue_week": paid.filter(created_at__date__gte=week_start).aggregate(v=Sum("total"))["v"] or 0,
        "revenue_month": paid.filter(created_at__date__gte=month_start).aggregate(v=Sum("total"))["v"] or 0,
        "orders_total": Order.objects.count(),
        "orders_pending": Order.objects.filter(status=Order.Status.PENDING).count(),
        "orders_completed": Order.objects.filter(status=Order.Status.DELIVERED).count(),
        "customers_total": User.objects.filter(role=User.Role.CUSTOMER).count(),
        "products_total": Product.objects.filter(is_active=True).count(),
        "low_stock": Product.objects.filter(
            is_active=True, stock_quantity__gt=0, stock_quantity__lte=F("low_stock_threshold")
        ).count(),
        "out_of_stock": Product.objects.filter(is_active=True, stock_quantity=0).count(),
        "aov": 0,
    }


@staff_required
def overview(request):
    summary = _summary()
    paid_count = Order.objects.filter(payment_status=Order.PaymentStatus.PAID).count()
    summary["aov"] = (summary["revenue_total"] / paid_count) if paid_count else 0
    labels, revenue, orders = _revenue_series(30)

    status_counts = list(
        Order.objects.values("status").annotate(count=Count("id")).order_by("-count")
    )
    status_labels = [dict(Order.Status.choices).get(item["status"], item["status"]) for item in status_counts]
    status_values = [item["count"] for item in status_counts]

    top_products = (
        OrderItem.objects.filter(order__payment_status=Order.PaymentStatus.PAID)
        .values("product_name")
        .annotate(units=Sum("quantity"), revenue=Sum("line_total"))
        .order_by("-revenue")[:6]
    )
    category_sales = (
        OrderItem.objects.filter(order__payment_status=Order.PaymentStatus.PAID)
        .values("product__category__name")
        .annotate(revenue=Sum("line_total"))
        .order_by("-revenue")[:6]
    )
    return render(
        request,
        "dashboard/overview.html",
        {
            "summary": summary,
            "chart_labels": json.dumps(labels),
            "chart_revenue": json.dumps(revenue),
            "chart_orders": json.dumps(orders),
            "status_labels": json.dumps(status_labels),
            "status_values": json.dumps(status_values),
            "recent_orders": Order.objects.select_related("user").order_by("-created_at")[:8],
            "recent_payments": Payment.objects.filter(status=Payment.Status.SUCCESS)
            .select_related("order")
            .order_by("-completed_at")[:8],
            "low_stock_products": Product.objects.filter(
                is_active=True, stock_quantity__lte=F("low_stock_threshold")
            ).order_by("stock_quantity")[:8],
            "top_products": top_products,
            "category_sales": category_sales,
            "pending_reviews": Review.objects.filter(is_approved=False).count(),
        },
    )


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
@staff_required
def product_list(request):
    products = Product.objects.select_related("category", "brand").prefetch_related("images")
    q = request.GET.get("q", "").strip()
    if q:
        products = products.filter(
            Q(name__icontains=q) | Q(sku__icontains=q) | Q(brand__name__icontains=q)
        )
    category = request.GET.get("category")
    if category:
        products = products.filter(category__slug=category)
    status = request.GET.get("status")
    if status == "active":
        products = products.filter(is_active=True)
    elif status == "inactive":
        products = products.filter(is_active=False)
    elif status == "low":
        products = products.filter(stock_quantity__lte=F("low_stock_threshold"))
    elif status == "out":
        products = products.filter(stock_quantity=0)
    featured = request.GET.get("featured")
    if featured == "1":
        products = products.filter(is_featured=True)
    products = products.order_by("-created_at")
    page, items = _paginate(request, products)
    return render(
        request,
        "dashboard/products/list.html",
        {
            "page_obj": page,
            "products": items,
            "categories": Category.objects.all(),
            "q": q,
            "category": category or "",
            "status": status or "",
            "featured": featured or "",
        },
    )


def _save_uploaded_images(product, files, request):
    if not files:
        return
    existing = product.images.count()
    for uploaded in files[: max(0, 8 - existing)]:
        image = ProductImage(product=product, image=uploaded, alt_text=product.name)
        try:
            image.full_clean()
            image.save()
        except Exception as exc:
            messages.error(request, f"Image {getattr(uploaded, 'name', '')} could not be uploaded: {exc}")


@staff_required
def product_create(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    formset = ProductSpecificationFormSet(request.POST or None, instance=Product())
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        product = form.save()
        formset.instance = product
        formset.save()
        _save_uploaded_images(product, form.cleaned_data.get("images"), request)
        messages.success(request, f"Product “{product.name}” created.")
        return redirect("dashboard:product_edit", pk=product.pk)
    if request.method == "POST" and not formset.is_valid():
        messages.error(request, "Please fix the specification rows.")
    return render(
        request,
        "dashboard/products/form.html",
        {"form": form, "formset": formset, "product": None, "title": "Add product"},
    )


@staff_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    formset = ProductSpecificationFormSet(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        product = form.save()
        formset.save()
        _save_uploaded_images(product, form.cleaned_data.get("images"), request)
        messages.success(request, "Product updated.")
        return redirect("dashboard:product_edit", pk=product.pk)
    return render(
        request,
        "dashboard/products/form.html",
        {
            "form": form,
            "formset": formset,
            "product": product,
            "title": f"Edit: {product.name}",
            "image_form": ProductImageUploadForm(),
        },
    )


@staff_required
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    name = product.name
    product.delete()
    messages.success(request, f"Product “{name}” deleted.")
    return redirect("dashboard:product_list")


@staff_required
@require_POST
def product_toggle(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.is_active = not product.is_active
    product.is_featured = product.is_featured if product.is_active else False
    product.save(update_fields=["is_active", "is_featured", "updated_at"])
    messages.success(request, f"{product.name} is now {'active' if product.is_active else 'inactive'}.")
    return redirect(request.META.get("HTTP_REFERER", reverse("dashboard:product_list")))


@staff_required
@require_POST
def product_image_upload(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductImageUploadForm(request.POST, request.FILES)
    if form.is_valid():
        _save_uploaded_images(product, form.cleaned_data["images"], request)
        messages.success(request, "Images uploaded.")
    else:
        messages.error(request, "Please choose valid image files.")
    return redirect("dashboard:product_edit", pk=pk)


@staff_required
@require_POST
def product_image_delete(request, pk, image_id):
    image = get_object_or_404(ProductImage, pk=image_id, product_id=pk)
    image.image.delete(save=False)
    image.delete()
    messages.success(request, "Image removed.")
    return redirect("dashboard:product_edit", pk=pk)


@staff_required
@require_POST
def product_image_primary(request, pk, image_id):
    image = get_object_or_404(ProductImage, pk=image_id, product_id=pk)
    image.is_primary = True
    image.save()
    messages.success(request, "Primary image updated.")
    return redirect("dashboard:product_edit", pk=pk)


@staff_required
def category_specs_api(request, pk):
    category = get_object_or_404(Category, pk=pk)
    fields = category.spec_fields.all().values("id", "label", "key", "unit", "input_type", "options")
    return JsonResponse({"fields": list(fields)})


# ---------------------------------------------------------------------------
# Categories / brands / specification schema
# ---------------------------------------------------------------------------
@staff_required
def category_list(request):
    categories = Category.objects.select_related("parent").order_by(
        "parent__name", "sort_order", "name"
    )
    return render(request, "dashboard/categories/list.html", {"categories": categories})


@staff_required
def category_create(request):
    form = CategoryForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        cache.delete("nav_categories")
        messages.success(request, "Category created.")
        return redirect("dashboard:category_list")
    return render(request, "dashboard/categories/form.html", {"form": form, "title": "Add category"})


@staff_required
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST or None, request.FILES or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        cache.delete("nav_categories")
        messages.success(request, "Category updated.")
        return redirect("dashboard:category_list")
    return render(request, "dashboard/categories/form.html", {"form": form, "category": category, "title": "Edit category"})


@staff_required
@require_POST
def category_delete(request, pk):
    from django.db.models import ProtectedError

    category = get_object_or_404(Category, pk=pk)
    try:
        category.delete()
        cache.delete("nav_categories")
        messages.success(request, "Category deleted.")
    except ProtectedError:
        messages.error(request, "This category has products. Move or delete those products first.")
    return redirect("dashboard:category_list")


@staff_required
def brand_list(request):
    brands = Brand.objects.order_by("name")
    return render(request, "dashboard/brands/list.html", {"brands": brands})


@staff_required
def brand_create(request):
    form = BrandForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Brand created.")
        return redirect("dashboard:brand_list")
    return render(request, "dashboard/brands/form.html", {"form": form, "title": "Add brand"})


@staff_required
def brand_edit(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    form = BrandForm(request.POST or None, request.FILES or None, instance=brand)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Brand updated.")
        return redirect("dashboard:brand_list")
    return render(request, "dashboard/brands/form.html", {"form": form, "brand": brand, "title": "Edit brand"})


@staff_required
@require_POST
def brand_delete(request, pk):
    from django.db.models import ProtectedError

    brand = get_object_or_404(Brand, pk=pk)
    try:
        brand.delete()
        messages.success(request, "Brand deleted.")
    except ProtectedError:
        messages.error(request, "This brand has products and cannot be deleted.")
    return redirect("dashboard:brand_list")


@staff_required
def specfield_list(request):
    fields = SpecificationField.objects.select_related("category")
    category = request.GET.get("category")
    if category:
        fields = fields.filter(category__slug=category)
    return render(
        request,
        "dashboard/specfields/list.html",
        {"fields": fields, "categories": Category.objects.all(), "category": category or ""},
    )


@staff_required
def specfield_create(request):
    form = SpecificationFieldForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Specification field added.")
        return redirect("dashboard:specfield_list")
    return render(request, "dashboard/specfields/form.html", {"form": form, "title": "Add specification field"})


@staff_required
def specfield_edit(request, pk):
    field = get_object_or_404(SpecificationField, pk=pk)
    form = SpecificationFieldForm(request.POST or None, instance=field)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Specification field updated.")
        return redirect("dashboard:specfield_list")
    return render(
        request, "dashboard/specfields/form.html", {"form": form, "field": field, "title": "Edit specification field"}
    )


@staff_required
@require_POST
def specfield_delete(request, pk):
    get_object_or_404(SpecificationField, pk=pk).delete()
    messages.success(request, "Specification field deleted.")
    return redirect("dashboard:specfield_list")


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
@staff_required
def order_list(request):
    orders = Order.objects.select_related("user").prefetch_related("items").order_by("-created_at")
    q = request.GET.get("q", "").strip()
    if q:
        orders = orders.filter(
            Q(order_number__icontains=q)
            | Q(email__icontains=q)
            | Q(full_name__icontains=q)
            | Q(phone__icontains=q)
        )
    status = request.GET.get("status")
    if status in dict(Order.Status.choices):
        orders = orders.filter(status=status)
    payment_status = request.GET.get("payment_status")
    if payment_status in dict(Order.PaymentStatus.choices):
        orders = orders.filter(payment_status=payment_status)
    date_from = parse_date(request.GET.get("from", ""))
    date_to = parse_date(request.GET.get("to", ""))
    if date_from:
        orders = orders.filter(created_at__date__gte=date_from)
    if date_to:
        orders = orders.filter(created_at__date__lte=date_to)
    page, items = _paginate(request, orders)
    return render(
        request,
        "dashboard/orders/list.html",
        {
            "page_obj": page,
            "orders": items,
            "statuses": Order.Status.choices,
            "payment_statuses": Order.PaymentStatus.choices,
            "q": q,
            "status": status or "",
            "payment_status": payment_status or "",
            "date_from": request.GET.get("from", ""),
            "date_to": request.GET.get("to", ""),
        },
    )


@staff_required
def order_detail(request, order_number):
    order = get_object_or_404(
        Order.objects.select_related("user", "shipping_method")
        .prefetch_related("items__product", "payments__transactions", "status_history__changed_by", "coupon_usages"),
        order_number=order_number,
    )
    form = OrderStatusForm(initial={"status": order.status})
    return render(
        request,
        "dashboard/orders/detail.html",
        {
            "order": order,
            "form": form,
            "statuses": Order.Status.choices,
            "payments": order.payments.all(),
        },
    )


@staff_required
@require_POST
def order_update_status(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)
    form = OrderStatusForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Invalid status update.")
        return redirect("dashboard:order_detail", order_number=order.order_number)
    new_status = form.cleaned_data["status"]
    note = form.cleaned_data.get("note", "")
    try:
        if new_status == Order.Status.CANCELLED:
            cancel_order(order, changed_by=request.user, reason=note or "Cancelled by staff")
        elif new_status == Order.Status.REFUNDED:
            if not request.user.is_administrator and not request.user.is_superuser:
                messages.error(request, "Only administrators can issue refunds.")
                return redirect("dashboard:order_detail", order_number=order.order_number)
            _refund_order(order, request.user, note)
        else:
            order.set_status(new_status, note=note, changed_by=request.user)
            if new_status == Order.Status.DELIVERED and order.payment_method == Order.PaymentMethod.COD:
                mark_cod_collected(order, collected_by=request.user)
    except CheckoutError as exc:
        messages.error(request, str(exc))
        return redirect("dashboard:order_detail", order_number=order.order_number)

    update_fields = []
    if form.cleaned_data.get("tracking_number"):
        order.tracking_number = form.cleaned_data["tracking_number"]
        update_fields.append("tracking_number")
    if form.cleaned_data.get("courier"):
        order.courier = form.cleaned_data["courier"]
        update_fields.append("courier")
    if update_fields:
        order.save(update_fields=update_fields)
    if order.user_id:
        Notification.push(
            order.user,
            f"Order {order.order_number} updated",
            f"Your order is now marked as {order.get_status_display()}.",
            url=order.get_absolute_url(),
            kind=Notification.Kind.ORDER,
        )
    send_mail(
        f"Order {order.order_number}: {order.get_status_display()}",
        f"Hi {order.full_name},\n\nYour order {order.order_number} is now {order.get_status_display()}."
        + (f"\nTracking: {order.courier} {order.tracking_number}" if order.tracking_number else "")
        + "\n\n— Team Voltiq",
        settings.DEFAULT_FROM_EMAIL,
        [order.email],
        fail_silently=True,
    )
    messages.success(request, f"Order status updated to {order.get_status_display()}.")
    return redirect("dashboard:order_detail", order_number=order.order_number)


def _refund_order(order, by, note=""):
    with transaction.atomic():
        if order.status not in {Order.Status.CANCELLED, Order.Status.REFUNDED}:
            restock_order(order, changed_by=by)
        record_manual_refund(order, by=by, reason=note or "Refund approved by administrator")
        order.status = Order.Status.REFUNDED
        order.save(update_fields=["status", "updated_at"])
        from apps.orders.models import OrderStatusHistory

        OrderStatusHistory.objects.create(
            order=order, status=Order.Status.REFUNDED, note=note or "Refund processed.", changed_by=by
        )
        if order.user_id:
            Notification.push(
                order.user,
                "Refund processed",
                f"A refund for order {order.order_number} has been recorded.",
                url=order.get_absolute_url(),
                kind=Notification.Kind.PAYMENT,
            )


@staff_required
@require_POST
def order_mark_paid(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)
    if order.payment_status == Order.PaymentStatus.PAID:
        messages.info(request, "This order is already paid.")
        return redirect("dashboard:order_detail", order_number=order.order_number)
    with transaction.atomic():
        payment = order.payments.filter(gateway__in=[Payment.Gateway.BANK, Payment.Gateway.COD]).order_by("-id").first()
        if not payment:
            payment = Payment.objects.create(
                order=order,
                gateway=order.payment_method if order.payment_method in {"bank", "cod"} else Payment.Gateway.BANK,
                amount=order.total,
                status=Payment.Status.PENDING,
                attempt_number=order.payments.count() + 1,
            )
        payment.gateway_ref = f"MANUAL-{request.user.pk}"
        payment.mark_success(
            payload={"manual": True, "verified_by": request.user.email, "note": "Marked paid in dashboard"},
            gateway_ref=payment.gateway_ref,
        )
    messages.success(request, "Payment marked as received.")
    return redirect("dashboard:order_detail", order_number=order.order_number)


@staff_required
def order_invoice(request, order_number):
    """Dashboard invoice delegates to the same secure PDF generator."""
    from apps.orders import views as order_views

    return order_views.invoice_pdf(request, order_number)


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------
@staff_required
def customer_list(request):
    customers = User.objects.filter(role=User.Role.CUSTOMER).annotate(
        order_count=Count("orders"),
        spent=Sum("orders__total", filter=Q(orders__payment_status=Order.PaymentStatus.PAID)),
    )
    q = request.GET.get("q", "").strip()
    if q:
        customers = customers.filter(
            Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(phone__icontains=q)
        )
    status = request.GET.get("status")
    if status == "active":
        customers = customers.filter(is_suspended=False)
    elif status == "suspended":
        customers = customers.filter(is_suspended=True)
    customers = customers.order_by("-date_joined")
    page, items = _paginate(request, customers)
    return render(
        request,
        "dashboard/customers/list.html",
        {"page_obj": page, "customers": items, "q": q, "status": status or ""},
    )


@staff_required
def customer_detail(request, pk):
    customer = get_object_or_404(User, pk=pk)
    if customer.is_staff and not request.user.is_administrator:
        messages.error(request, "Only administrators can view staff accounts.")
        return redirect("dashboard:customer_list")
    orders = customer.orders.prefetch_related("items").order_by("-created_at")
    spent = orders.filter(payment_status=Order.PaymentStatus.PAID).aggregate(v=Sum("total"))["v"] or 0
    return render(
        request,
        "dashboard/customers/detail.html",
        {
            "customer": customer,
            "orders": orders[:20],
            "spent": spent,
            "addresses": customer.addresses.all(),
            "reviews": customer.reviews.select_related("product")[:10],
        },
    )


@admin_required
@require_POST
def customer_toggle_suspension(request, pk):
    customer = get_object_or_404(User, pk=pk)
    if customer.is_superuser or customer.is_administrator:
        messages.error(request, "Administrator accounts cannot be suspended.")
        return redirect("dashboard:customer_detail", pk=pk)
    customer.is_suspended = not customer.is_suspended
    customer.suspension_reason = request.POST.get("reason", "")[:255] if customer.is_suspended else ""
    customer.save(update_fields=["is_suspended", "suspension_reason"])
    messages.success(request, f"{customer.email} is now {'suspended' if customer.is_suspended else 'active'}.")
    return redirect("dashboard:customer_detail", pk=pk)


@admin_required
@require_POST
def customer_set_role(request, pk):
    customer = get_object_or_404(User, pk=pk)
    if customer.is_superuser:
        messages.error(request, "Superuser roles cannot be changed here.")
        return redirect("dashboard:customer_detail", pk=pk)
    role = request.POST.get("role")
    if role not in {User.Role.CUSTOMER, User.Role.STAFF, User.Role.ADMIN}:
        messages.error(request, "Invalid role.")
        return redirect("dashboard:customer_detail", pk=pk)
    customer.role = role
    customer.is_staff = role in {User.Role.STAFF, User.Role.ADMIN}
    customer.save(update_fields=["role", "is_staff"])
    messages.success(request, f"Role updated to {customer.get_role_display()}.")
    return redirect("dashboard:customer_detail", pk=pk)


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------
@staff_required
def inventory_list(request):
    products = Product.objects.select_related("category", "brand")
    q = request.GET.get("q", "").strip()
    if q:
        products = products.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    filter_by = request.GET.get("filter")
    if filter_by == "low":
        products = products.filter(stock_quantity__lte=F("low_stock_threshold"), stock_quantity__gt=0)
    elif filter_by == "out":
        products = products.filter(stock_quantity=0)
    products = products.order_by("stock_quantity")
    page, items = _paginate(request, products)
    return render(
        request,
        "dashboard/inventory/list.html",
        {
            "page_obj": page,
            "products": items,
            "q": q,
            "filter": filter_by or "",
            "low_count": Product.objects.filter(
                stock_quantity__gt=0, stock_quantity__lte=F("low_stock_threshold")
            ).count(),
            "out_count": Product.objects.filter(stock_quantity=0).count(),
        },
    )


@staff_required
def inventory_adjust(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = StockAdjustForm(
        request.POST or None,
        initial={"product_id": product.pk, "new_quantity": product.stock_quantity},
    )
    if request.method == "POST" and form.is_valid():
        try:
            set_stock(
                product,
                form.cleaned_data["new_quantity"],
                reason=form.cleaned_data["reason"],
                reference=form.cleaned_data.get("reference", ""),
                user=request.user,
            )
            messages.success(request, f"Stock updated for {product.name}.")
            return redirect("dashboard:inventory_adjust", pk=product.pk)
        except StockError as exc:
            messages.error(request, str(exc))
    history = product.stock_history.select_related("changed_by", "order")[:30]
    return render(
        request,
        "dashboard/inventory/adjust.html",
        {"product": product, "form": form, "history": history},
    )


@staff_required
def stock_history(request):
    history = StockHistory.objects.select_related("product", "changed_by", "order")
    q = request.GET.get("q", "").strip()
    if q:
        history = history.filter(Q(product__name__icontains=q) | Q(product__sku__icontains=q) | Q(reference__icontains=q))
    reason = request.GET.get("reason")
    if reason in dict(StockHistory.Reason.choices):
        history = history.filter(reason=reason)
    page, items = _paginate(request, history, 30)
    return render(
        request,
        "dashboard/inventory/history.html",
        {
            "page_obj": page,
            "history": items,
            "q": q,
            "reason": reason or "",
            "reasons": StockHistory.Reason.choices,
        },
    )


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
@staff_required
def reports(request):
    today = timezone.localdate()
    start = parse_date(request.GET.get("from", "")) or (today - timedelta(days=29))
    end = parse_date(request.GET.get("to", "")) or today
    if start > end:
        start, end = end, start
    if (end - start).days > 365:
        start = end - timedelta(days=365)

    paid = Order.objects.filter(
        payment_status=Order.PaymentStatus.PAID,
        created_at__date__gte=start,
        created_at__date__lte=end,
    )
    totals = paid.aggregate(revenue=Sum("total"), orders=Count("id"))
    revenue = totals["revenue"] or 0
    order_count = totals["orders"] or 0
    units = OrderItem.objects.filter(order__in=paid).aggregate(v=Sum("quantity"))["v"] or 0
    customers_new = User.objects.filter(
        role=User.Role.CUSTOMER, date_joined__date__gte=start, date_joined__date__lte=end
    ).count()

    labels, series_revenue, series_orders = _revenue_series_for(start, end)
    top_products = (
        OrderItem.objects.filter(order__in=paid)
        .values("product_name", "sku")
        .annotate(units=Sum("quantity"), revenue=Sum("line_total"))
        .order_by("-revenue")[:10]
    )
    categories = (
        OrderItem.objects.filter(order__in=paid)
        .values("product__category__name")
        .annotate(revenue=Sum("line_total"), units=Sum("quantity"))
        .order_by("-revenue")[:8]
    )
    payments = (
        paid.values("payment_method").annotate(count=Count("id"), revenue=Sum("total")).order_by("-revenue")
    )
    payment_labels = [dict(Order.PaymentMethod.choices).get(p["payment_method"], p["payment_method"]).title() for p in payments]
    payment_values = [float(p["revenue"]) for p in payments]
    status_breakdown = Order.objects.filter(created_at__date__gte=start, created_at__date__lte=end).values(
        "status"
    ).annotate(count=Count("id"))
    top_customers = (
        User.objects.filter(orders__in=paid)
        .annotate(spent=Sum("orders__total"), order_count=Count("orders"))
        .order_by("-spent")[:8]
    )
    return render(
        request,
        "dashboard/reports.html",
        {
            "start": start,
            "end": end,
            "revenue": revenue,
            "order_count": order_count,
            "aov": (revenue / order_count) if order_count else 0,
            "units": units,
            "customers_new": customers_new,
            "chart_labels": json.dumps(labels),
            "chart_revenue": json.dumps(series_revenue),
            "chart_orders": json.dumps(series_orders),
            "payment_labels": json.dumps(payment_labels),
            "payment_values": json.dumps(payment_values),
            "status_labels": json.dumps(
                [dict(Order.Status.choices).get(s["status"], s["status"]) for s in status_breakdown]
            ),
            "status_values": json.dumps([s["count"] for s in status_breakdown]),
            "top_products": top_products,
            "categories": categories,
            "top_customers": top_customers,
            "payment_breakdown": payments,
        },
    )


def _revenue_series_for(start, end):
    rows = (
        Order.objects.filter(
            payment_status=Order.PaymentStatus.PAID,
            created_at__date__gte=start,
            created_at__date__lte=end,
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(revenue=Sum("total"), orders=Count("id"))
        .order_by("day")
    )
    mapping = {row["day"]: row for row in rows}
    labels, revenue, orders = [], [], []
    day = start
    while day <= end:
        row = mapping.get(day)
        labels.append(day.strftime("%d %b"))
        revenue.append(float(row["revenue"]) if row else 0)
        orders.append(row["orders"] if row else 0)
        day += timedelta(days=1)
    return labels, revenue, orders


def _csv_safe(value):
    value = "" if value is None else str(value)
    if value.startswith(("=", "+", "-", "@")):
        value = "'" + value
    return value


@staff_required
def export_orders_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="voltiq-orders.csv"'
    writer = csv.writer(response)
    writer.writerow(
        ["Order", "Date", "Customer", "Email", "Status", "Payment status", "Method", "Subtotal", "Discount", "Shipping", "Total"]
    )
    for order in Order.objects.order_by("-created_at").iterator():
        writer.writerow(
            [
                _csv_safe(order.order_number),
                timezone.localtime(order.created_at).strftime("%Y-%m-%d %H:%M"),
                _csv_safe(order.full_name),
                _csv_safe(order.email),
                order.status,
                order.payment_status,
                order.payment_method,
                order.subtotal,
                order.discount_amount,
                order.shipping_fee,
                order.total,
            ]
        )
    return response


@staff_required
def export_newsletter_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="voltiq-newsletter.csv"'
    writer = csv.writer(response)
    writer.writerow(["Email", "Name", "Subscribed", "Active"])
    for subscriber in NewsletterSubscription.objects.all().iterator():
        writer.writerow(
            [_csv_safe(subscriber.email), _csv_safe(subscriber.name), subscriber.created_at, subscriber.is_active]
        )
    return response


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------
@staff_required
def review_list(request):
    reviews = Review.objects.select_related("product", "user")
    status = request.GET.get("status")
    if status == "pending":
        reviews = reviews.filter(is_approved=False)
    elif status == "approved":
        reviews = reviews.filter(is_approved=True)
    rating = request.GET.get("rating")
    if rating in {"1", "2", "3", "4", "5"}:
        reviews = reviews.filter(rating=int(rating))
    page, items = _paginate(request, reviews)
    return render(
        request,
        "dashboard/reviews/list.html",
        {"page_obj": page, "reviews": items, "status": status or "", "rating": rating or ""},
    )


@staff_required
@require_POST
def review_toggle(request, pk):
    review = get_object_or_404(Review, pk=pk)
    review.is_approved = not review.is_approved
    review.save(update_fields=["is_approved", "updated_at"])
    from apps.reviews.signals import refresh_product_rating

    refresh_product_rating(review.product_id)
    messages.success(request, "Review visibility updated.")
    return redirect(request.META.get("HTTP_REFERER", reverse("dashboard:review_list")))


@staff_required
@require_POST
def review_delete(request, pk):
    review = get_object_or_404(Review, pk=pk)
    review.delete()
    messages.success(request, "Review deleted.")
    return redirect(request.META.get("HTTP_REFERER", reverse("dashboard:review_list")))


# ---------------------------------------------------------------------------
# Coupons / newsletter / messages
# ---------------------------------------------------------------------------
@staff_required
def coupon_list(request):
    coupons = Coupon.objects.annotate(order_count=Count("orders")).order_by("-created_at")
    page, items = _paginate(request, coupons)
    return render(request, "dashboard/coupons/list.html", {"page_obj": page, "coupons": items})


@staff_required
def coupon_create(request):
    form = CouponForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Coupon created.")
        return redirect("dashboard:coupon_list")
    return render(request, "dashboard/coupons/form.html", {"form": form, "title": "Create coupon"})


@staff_required
def coupon_edit(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    form = CouponForm(request.POST or None, instance=coupon)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Coupon updated.")
        return redirect("dashboard:coupon_list")
    return render(request, "dashboard/coupons/form.html", {"form": form, "coupon": coupon, "title": "Edit coupon"})


@staff_required
@require_POST
def coupon_delete(request, pk):
    get_object_or_404(Coupon, pk=pk).delete()
    messages.success(request, "Coupon deleted.")
    return redirect("dashboard:coupon_list")


@staff_required
def newsletter_list(request):
    subscribers = NewsletterSubscription.objects.all()
    q = request.GET.get("q", "").strip()
    if q:
        subscribers = subscribers.filter(Q(email__icontains=q) | Q(name__icontains=q))
    active = request.GET.get("active")
    if active == "1":
        subscribers = subscribers.filter(is_active=True)
    elif active == "0":
        subscribers = subscribers.filter(is_active=False)
    page, items = _paginate(request, subscribers, 30)
    return render(
        request,
        "dashboard/newsletter.html",
        {"page_obj": page, "subscribers": items, "q": q, "active": active or ""},
    )


@staff_required
def contact_messages(request):
    messages_qs = ContactMessage.objects.all()
    status = request.GET.get("status")
    if status in dict(ContactMessage.Status.choices):
        messages_qs = messages_qs.filter(status=status)
    page, items = _paginate(request, messages_qs, 20)
    return render(
        request,
        "dashboard/messages.html",
        {"page_obj": page, "contact_messages": items, "status": status or "", "statuses": ContactMessage.Status.choices},
    )


@staff_required
@require_POST
def contact_message_status(request, pk):
    message = get_object_or_404(ContactMessage, pk=pk)
    status = request.POST.get("status")
    if status in dict(ContactMessage.Status.choices):
        message.status = status
        message.save(update_fields=["status"])
        messages.success(request, "Message status updated.")
    return redirect(request.META.get("HTTP_REFERER", reverse("dashboard:contact_messages")))


# ---------------------------------------------------------------------------
# Store settings
# ---------------------------------------------------------------------------
@admin_required
def store_settings(request):
    site = SiteSetting.load()
    form = SiteSettingForm(request.POST or None, instance=site)
    shipping_form = ShippingMethodForm(prefix="shipping")
    if request.method == "POST":
        if request.POST.get("form_type") == "shipping":
            shipping_form = ShippingMethodForm(request.POST, prefix="shipping")
            if shipping_form.is_valid():
                shipping_form.save()
                messages.success(request, "Shipping method added.")
                return redirect("dashboard:store_settings")
        elif form.is_valid():
            form.save()
            cache.delete("site_setting")
            messages.success(request, "Store settings updated.")
            return redirect("dashboard:store_settings")
    return render(
        request,
        "dashboard/settings.html",
        {
            "form": form,
            "shipping_form": shipping_form,
            "shipping_methods": ShippingMethod.objects.all().order_by("sort_order"),
        },
    )


@admin_required
def shipping_edit(request, pk):
    method = get_object_or_404(ShippingMethod, pk=pk)
    form = ShippingMethodForm(request.POST or None, instance=method)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Shipping method updated.")
        return redirect("dashboard:store_settings")
    return render(request, "dashboard/shipping_form.html", {"form": form, "method": method})


@admin_required
@require_POST
def shipping_delete(request, pk):
    method = get_object_or_404(ShippingMethod, pk=pk)
    if method.orders.exists():
        method.is_active = False
        method.save(update_fields=["is_active"])
        messages.warning(request, "This method is used by orders, so it was deactivated instead of deleted.")
    else:
        method.delete()
        messages.success(request, "Shipping method deleted.")
    return redirect("dashboard:store_settings")
