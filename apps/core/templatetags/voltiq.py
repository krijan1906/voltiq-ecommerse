from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from decimal import Decimal, InvalidOperation

register = template.Library()


@register.filter
def npr(value):
    """Nepali rupee formatting without unnecessary decimals."""
    try:
        amount = Decimal(str(value or 0))
    except (InvalidOperation, ValueError):
        return "Rs. 0"
    if amount == amount.to_integral_value():
        return f"Rs. {amount:,.0f}"
    return f"Rs. {amount:,.2f}"


@register.filter
def star_percent(rating):
    try:
        return min(100, max(0, float(rating or 0) / 5 * 100))
    except (TypeError, ValueError):
        return 0


@register.filter
def multiply(value, arg):
    try:
        return Decimal(str(value or 0)) * Decimal(str(arg or 0))
    except (InvalidOperation, ValueError):
        return 0


@register.filter
def field_class(field, css):
    existing = field.field.widget.attrs.get("class", "")
    field.field.widget.attrs["class"] = f"{existing} {css}".strip()
    return field


@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """Rebuild the query string preserving existing filters (used by pagination)."""
    request = context.get("request")
    if not request:
        return ""
    params = request.GET.copy()
    for key, value in kwargs.items():
        if value is None or value == "":
            params.pop(key, None)
        else:
            params[key] = value
    if "page" not in kwargs:
        params.pop("page", None)
    return params.urlencode()


@register.simple_tag
def icon(name, css="icon"):
    return format_html(
        '<svg class="{}" aria-hidden="true" focusable="false"><use href="#i-{}"></use></svg>', css, name
    )


@register.simple_tag
def active_link(request, url_name):
    if not request:
        return ""
    try:
        match = request.resolver_match
        if match and match.view_name == url_name:
            return "is-active"
    except Exception:
        pass
    return ""


@register.filter
def get_item(mapping, key):
    if hasattr(mapping, "get"):
        return mapping.get(key)
    return None


@register.filter
def percentage_of(value, total):
    try:
        if not total:
            return 0
        return round(float(value) / float(total) * 100)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0
