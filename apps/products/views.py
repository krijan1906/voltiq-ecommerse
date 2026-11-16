from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.categories.models import Brand, Category
from apps.products.models import Product
from apps.reviews.forms import ReviewForm
from apps.reviews.models import Review

PRICE_EXPR = DecimalField(max_digits=12, decimal_places=2)


def _to_decimal(raw):
    try:
        value = Decimal(str(raw).replace(",", "").strip())
        return value if value >= 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _facets(queryset):
    def distinct_values(field):
        values = (
            queryset.exclude(**{f"{field}__isnull": True})
            .exclude(**{field: ""})
            .values_list(field, flat=True)
            .distinct()
            .order_by(field)
        )
        return [v for v in values if v][:40]

    return {
        "rams": distinct_values("ram"),
        "storages": distinct_values("storage"),
        "processors": distinct_values("processor"),
        "gpus": distinct_values("gpu"),
        "conditions": Product.Condition.choices,
    }


def product_list(request):
    base = Product.objects.active().with_listing_data()
    q = (request.GET.get("q") or "").strip()[:150]
    if q:
        base = base.search(q)

    selected_category = None
    category_slug = request.GET.get("category", "").strip()
    if category_slug:
        selected_category = Category.objects.filter(slug=category_slug, is_active=True).first()
        if selected_category:
            descendant_ids = list(
                selected_category.children.filter(is_active=True).values_list("id", flat=True)
            )
            base = base.filter(category_id__in=[selected_category.id, *descendant_ids])

    selected_brands = [b for b in request.GET.getlist("brand") if b][:12]
    if selected_brands:
        base = base.filter(brand__slug__in=selected_brands)
    selected_rams = [v for v in request.GET.getlist("ram") if v][:12]
    if selected_rams:
        base = base.filter(ram__in=selected_rams)
    selected_storages = [v for v in request.GET.getlist("storage") if v][:12]
    if selected_storages:
        base = base.filter(storage__in=selected_storages)
    selected_processors = [v for v in request.GET.getlist("processor") if v][:12]
    if selected_processors:
        base = base.filter(processor__in=selected_processors)
    selected_gpus = [v for v in request.GET.getlist("gpu") if v][:12]
    if selected_gpus:
        base = base.filter(gpu__in=selected_gpus)

    min_price = _to_decimal(request.GET.get("min_price"))
    max_price = _to_decimal(request.GET.get("max_price"))
    if min_price is not None and max_price is not None and min_price > max_price:
        min_price, max_price = max_price, min_price
    base = base.annotate(
        effective_price=Coalesce("discount_price", "price", output_field=PRICE_EXPR),
        discount_pct=ExpressionWrapper(
            (F("price") - Coalesce("discount_price", "price")) * 100 / F("price"),
            output_field=PRICE_EXPR,
        ),
    )
    if min_price is not None:
        base = base.filter(effective_price__gte=min_price)
    if max_price is not None:
        base = base.filter(effective_price__lte=max_price)

    rating = request.GET.get("rating")
    if rating in {"1", "2", "3", "4", "5"}:
        base = base.filter(rating_avg__gte=int(rating))

    availability = request.GET.get("availability")
    if availability == "in_stock":
        base = base.filter(stock_quantity__gt=0)
    elif availability == "out_of_stock":
        base = base.filter(stock_quantity__lte=0)

    discount = request.GET.get("discount")
    if discount in {"10", "20", "30", "40", "50"}:
        base = base.filter(discount_price__isnull=False, discount_pct__gte=int(discount))

    condition = request.GET.get("condition")
    if condition in dict(Product.Condition.choices):
        base = base.filter(condition=condition)

    sort = request.GET.get("sort", "recommended")
    sort_map = {
        "price_asc": ("effective_price", "name"),
        "price_desc": ("-effective_price", "name"),
        "newest": ("-created_at",),
        "bestselling": ("-sales_count", "-rating_avg"),
        "rating": ("-rating_avg", "-review_count"),
        "popular": ("-view_count", "-sales_count"),
        "recommended": ("-is_featured", "-sales_count", "-rating_avg"),
        "name": ("name",),
    }
    base = base.order_by(*sort_map.get(sort, sort_map["recommended"]))

    facets = _facets(Product.objects.active())
    paginator = Paginator(base, 24)
    page_obj = paginator.get_page(request.GET.get("page"))
    products = list(page_obj.object_list)

    # Fetch brand/category options once, avoiding N+1 queries.
    brands = Brand.objects.filter(is_active=True, products__is_active=True).annotate(
        product_total=Count("products", filter=Q(products__is_active=True))
    ).order_by("-product_total", "name")
    categories = Category.objects.filter(is_active=True, parent__isnull=True).prefetch_related("children")

    context = {
        "page_obj": page_obj,
        "products": products,
        "total_results": paginator.count,
        "facets": facets,
        "brands": brands,
        "categories": categories,
        "selected_category": selected_category,
        "selected_brands": selected_brands,
        "selected_rams": selected_rams,
        "selected_storages": selected_storages,
        "selected_processors": selected_processors,
        "selected_gpus": selected_gpus,
        "selected_condition": condition or "",
        "min_price": request.GET.get("min_price", ""),
        "max_price": request.GET.get("max_price", ""),
        "selected_rating": rating or "",
        "availability": availability or "",
        "discount": discount or "",
        "sort": sort,
        "query": q,
        "active_filters": _active_filters(request),
        "page_title": (
            q and f'Search results for "{q}"'
            or (selected_category and selected_category.name)
            or "All products"
        ),
    }
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.GET.get("partial") == "1"
    template = "products/_results.html" if is_ajax else "products/list.html"
    response = render(request, template, context)
    if is_ajax:
        response["X-Total-Count"] = str(paginator.count)
    return response


def _active_filters(request):
    labels = []
    mapping = {
        "category": "Category",
        "brand": "Brand",
        "ram": "RAM",
        "storage": "Storage",
        "processor": "Processor",
        "gpu": "GPU",
        "rating": "Rating",
        "availability": "Availability",
        "discount": "Discount",
        "condition": "Condition",
    }
    for key, label in mapping.items():
        values = request.GET.getlist(key)
        if values:
            display = ", ".join(v.replace("-", " ").title() for v in values if v)
            if display:
                labels.append(
                    {
                        "key": key,
                        "label": label,
                        "value": display,
                        "remove_url": _remove_filter_url(request, key),
                    }
                )
    if request.GET.get("min_price") or request.GET.get("max_price"):
        labels.append(
            {
                "key": "price",
                "label": "Price",
                "value": f"Rs. {request.GET.get('min_price') or 0} – {request.GET.get('max_price') or '∞'}",
                "remove_url": _remove_filter_url(request, "min_price", "max_price"),
            }
        )
    return labels


def _remove_filter_url(request, *keys):
    params = request.GET.copy()
    for key in keys:
        params.pop(key, None)
    params.pop("page", None)
    return f"?{params.urlencode()}" if params else "?"


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("brand", "category")
        .prefetch_related("images", "specifications", "reviews__user", "category__children"),
        slug=slug,
        is_active=True,
    )
    Product.objects.filter(pk=product.pk).update(view_count=F("view_count") + 1)
    product.view_count += 1
    reviews = product.reviews.filter(is_approved=True).select_related("user")
    review_form = ReviewForm()
    user_review = None
    can_review = False
    if request.user.is_authenticated:
        user_review = reviews.filter(user=request.user).first()
        from apps.orders.models import Order

        can_review = (
            Order.objects.filter(user=request.user, items__product=product)
            .exclude(status__in=[Order.Status.CANCELLED, Order.Status.REFUNDED])
            .exists()
        )
        if user_review:
            review_form = ReviewForm(instance=user_review)

    related = product.related_products(limit=8)
    specification_groups = {}
    for spec in product.specifications.all():
        group = spec.field.category.name if spec.field and spec.field.category_id else "General"
        specification_groups.setdefault(group, []).append(spec)

    recent = request.session.get("recently_viewed", [])
    recent = [pk for pk in recent if pk != product.pk][:7]
    request.session["recently_viewed"] = [product.pk, *recent]
    recent_products = (
        Product.objects.active().with_listing_data().filter(pk__in=recent).exclude(pk=product.pk)
    )

    rating_breakdown = []
    for stars in range(5, 0, -1):
        count = reviews.filter(rating=stars).count()
        rating_breakdown.append(
            {
                "stars": stars,
                "count": count,
                "percent": round(count / product.review_count * 100) if product.review_count else 0,
            }
        )

    context = {
        "product": product,
        "reviews": reviews[:12],
        "review_form": review_form,
        "user_review": user_review,
        "can_review": can_review,
        "related_products": related,
        "specification_groups": specification_groups,
        "rating_breakdown": rating_breakdown,
        "recent_products": recent_products,
    }
    return render(request, "products/detail.html", context)


@api_view(["GET"])
def search_suggestions(request):
    query = (request.query_params.get("q") or "").strip()[:100]
    if len(query) < 2:
        return Response({"query": query, "products": [], "categories": [], "brands": []})
    products = (
        Product.objects.active()
        .search(query)
        .with_listing_data()
        .order_by("-is_featured", "-sales_count")[:6]
    )
    categories = Category.objects.filter(name__icontains=query, is_active=True)[:4]
    brands = Brand.objects.filter(name__icontains=query, is_active=True)[:3]
    return Response(
        {
            "query": query,
            "products": [
                {
                    "name": p.name,
                    "url": p.get_absolute_url(),
                    "price": f"Rs. {p.current_price:,.0f}",
                    "compare_at": f"Rs. {p.price:,.0f}" if p.has_discount else "",
                    "image": p.primary_image_url,
                    "category": p.category.name,
                    "brand": p.brand.name,
                    "rating": float(p.rating_avg or 0),
                }
                for p in products
            ],
            "categories": [{"name": c.name, "url": c.get_absolute_url()} for c in categories],
            "brands": [{"name": b.name, "url": b.get_absolute_url()} for b in brands],
            "all_url": f"/products/?q={query}",
        }
    )
