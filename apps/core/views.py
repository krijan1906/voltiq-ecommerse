import datetime
import secrets
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import send_mail
from django.db.models import Avg, Count, ExpressionWrapper, F, DecimalField, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.categories.models import Brand, Category
from apps.core.forms import ContactForm, NewsletterForm
from apps.core.models import ContactMessage, NewsletterSubscription, SiteSetting
from apps.orders.models import Order
from apps.products.models import Product
from apps.reviews.models import Review


def _cached(key, loader, timeout=180):
    data = cache.get(key)
    if data is None:
        data = loader()
        cache.set(key, data, timeout)
    return data


def _home_data():
    active = Product.objects.active().with_listing_data()
    price_field = DecimalField(max_digits=12, decimal_places=2)
    deals = list(
        active.filter(discount_price__isnull=False)
        .annotate(
            discount_pct=ExpressionWrapper(
                (F("price") - F("discount_price")) * 100 / F("price"), output_field=price_field
            )
        )
        .order_by("-discount_pct")[:8]
    )
    categories = list(
        Category.objects.filter(is_active=True, parent__isnull=True, is_featured=True)
        .prefetch_related("children")
        .order_by("sort_order")[:10]
    )
    brands = list(Brand.objects.filter(is_active=True, is_featured=True).order_by("name")[:12])
    testimonials = list(
        Review.objects.approved()
        .filter(rating__gte=4)
        .select_related("user", "product")
        .order_by("-rating", "-created_at")[:6]
    )
    data = {
        "hero_products": list(active.filter(is_featured=True)[:3]),
        "categories": categories,
        "trending": list(active.order_by("-view_count", "-sales_count")[:8]),
        "bestsellers": list(active.order_by("-sales_count")[:8]),
        "latest": list(active.order_by("-created_at")[:8]),
        "deals": deals,
        "recommended": list(active.filter(rating_avg__gte=4).order_by("-rating_avg", "-review_count")[:8]),
        "new_arrivals": list(active.order_by("-created_at")[:4]),
        "brands": brands,
        "testimonials": testimonials,
        "stats": {
            "products": active.count(),
            "customers": _model_count("accounts", "User", is_staff=False),
            "orders": _model_count("orders", "Order"),
            "reviews": Review.objects.approved().count(),
        },
    }
    return data


def _model_count(app_label, model_name, **filters):
    from django.apps import apps

    return apps.get_model(app_label, model_name).objects.filter(**filters).count()


def home(request):
    data = _cached("home_page_data", _home_data, timeout=180)
    newsletter_form = NewsletterForm()
    deal_ends_at = (timezone.now() + datetime.timedelta(days=2, hours=6)).isoformat()
    return render(
        request,
        "home/index.html",
        {**data, "newsletter_form": newsletter_form, "deal_ends_at": deal_ends_at},
    )


@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def newsletter_subscribe(request):
    form = NewsletterForm(request.POST or None)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.content_type == "application/json"
    if request.method != "POST":
        return redirect("core:home")
    if not form.is_valid():
        message = "Please enter a valid email address."
        if is_ajax:
            return JsonResponse({"ok": False, "message": message}, status=400)
        messages.error(request, message)
        return redirect(request.META.get("HTTP_REFERER", reverse("core:home")))

    email = form.cleaned_data["email"]
    subscription, created = NewsletterSubscription.objects.get_or_create(
        email=email, defaults={"name": form.cleaned_data.get("name", ""), "token": secrets.token_urlsafe(24)}
    )
    if not created and not subscription.is_active:
        subscription.is_active = True
        subscription.unsubscribed_at = None
        if not subscription.token:
            subscription.token = secrets.token_urlsafe(24)
        subscription.save()
    if created:
        send_mail(
            "Welcome to the Voltiq insider list",
            "Thanks for subscribing. You'll be the first to hear about new drops, deals and "
            "expert buying guides.\n\n— Team Voltiq",
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=True,
        )
    message = "You're on the list! Watch your inbox for exclusive drops."
    if is_ajax:
        return JsonResponse({"ok": True, "message": message})
    messages.success(request, message)
    return redirect(request.META.get("HTTP_REFERER", reverse("core:home")))


def newsletter_unsubscribe(request, token):
    subscription = NewsletterSubscription.objects.filter(token=token).first()
    if subscription:
        subscription.is_active = False
        subscription.unsubscribed_at = timezone.now()
        subscription.save(update_fields=["is_active", "unsubscribed_at"])
        messages.success(request, "You have been unsubscribed from our newsletter.")
    else:
        messages.error(request, "That unsubscribe link is invalid.")
    return redirect("core:home")


def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        contact_message = form.save()
        send_mail(
            f"[Contact] {contact_message.subject}",
            f"From: {contact_message.name} <{contact_message.email}>\nPhone: {contact_message.phone}\n\n{contact_message.message}",
            settings.DEFAULT_FROM_EMAIL,
            [settings.SUPPORT_EMAIL],
            fail_silently=True,
        )
        messages.success(request, "Thanks for reaching out. Our team replies within one business day.")
        return redirect("core:contact")
    return render(request, "core/contact.html", {"form": form})


def about(request):
    return render(request, "core/about.html")


def faq(request):
    return render(request, "core/faq.html")


POLICY_CONTENT = {
    "privacy": {
        "title": "Privacy Policy",
        "eyebrow": "Your data, protected",
        "intro": "We collect only what we need to fulfil your order and improve your shopping experience. We never sell personal data.",
        "sections": [
            ("Information we collect", "Account details, delivery addresses, order history, and technical data such as IP and device information. Payment card data is never stored on our servers — payments are handled by eSewa, Khalti or your bank."),
            ("How we use it", "To process orders, deliver purchases, provide support, prevent fraud, and (with consent) send marketing updates. You can unsubscribe at any time."),
            ("Cookies", "We use essential session cookies for authentication and cart persistence, and privacy-friendly analytics cookies to understand storefront performance."),
            ("Data retention", "Order and tax records are retained as required by Nepalese law. Marketing preferences are retained until you withdraw consent."),
            ("Your rights", "You can access, correct, export or request deletion of your personal data by emailing support@voltiq.com.np. We respond within 30 days."),
        ],
    },
    "terms": {
        "title": "Terms of Service",
        "eyebrow": "Shopping with confidence",
        "intro": "By using Voltiq you agree to these terms. They exist to keep buying and selling clear and fair for everyone.",
        "sections": [
            ("Orders and pricing", "All prices are shown in Nepalese Rupees (NPR). We reserve the right to cancel orders resulting from pricing errors or suspected fraud, with a full refund."),
            ("Payments", "Online payments are verified server-side before an order is confirmed. Cash on delivery is available on eligible orders."),
            ("Warranty", "Products carry the warranty stated on the product page. Physical damage, liquid damage and unauthorised repairs are excluded."),
            ("Account responsibility", "You are responsible for keeping your password secure and for activity under your account. Notify us immediately of unauthorised access."),
            ("Limitation of liability", "Our liability is limited to the value of the product purchased, to the extent permitted by Nepalese law."),
        ],
    },
    "shipping": {
        "title": "Shipping & Delivery",
        "eyebrow": "Fast, tracked delivery",
        "intro": "We deliver across all seven provinces of Nepal with tracked courier partners.",
        "sections": [
            ("Kathmandu Valley", "Standard delivery in 1–2 business days. Express same-day delivery is available for orders placed before 12:00 PM."),
            ("Outside the valley", "Delivery in 3–7 business days depending on the district. Remote areas may take slightly longer."),
            ("Charges", "Standard delivery is free on orders over Rs. 10,000. Below that, a flat Rs. 250 applies. Express delivery is Rs. 500."),
            ("Tracking", "Once dispatched, you receive a tracking number and can follow the order from your account or the order tracking page."),
            ("Delivery inspection", "Please inspect sealed packaging on arrival. Report transit damage within 24 hours with photos so we can resolve it quickly."),
        ],
    },
    "returns": {
        "title": "Returns & Refunds",
        "eyebrow": "Easy, honest returns",
        "intro": "Changed your mind or received a faulty product? We make returns straightforward.",
        "sections": [
            ("7-day return window", "Unopened products in original packaging can be returned within 7 days of delivery. Opened electronics are eligible only for warranty defects."),
            ("Faulty products", "If a product is dead on arrival or develops a manufacturing fault, contact us within 7 days for a replacement or refund. Diagnostics may be required."),
            ("Refund timeline", "Approved refunds are processed to the original payment method within 5–7 business days. Cash on delivery refunds are made by bank transfer."),
            ("Non-returnable items", "Software licenses, digital gift cards, and hygiene products such as in-ear headphones that have been opened are non-returnable unless faulty."),
            ("How to start", "Open your order in Account → Orders and choose Request cancellation, or email support@voltiq.com.np with your order number."),
        ],
    },
}


def policy(request, slug):
    content = POLICY_CONTENT.get(slug)
    if not content:
        from django.http import Http404

        raise Http404("Page not found")
    return render(request, "core/policy.html", {"policy": content, "slug": slug})


def robots_txt(request):
    from django.http import HttpResponse

    return HttpResponse(
        "User-agent: *\nAllow: /\nDisallow: /dashboard/\nDisallow: /accounts/\n"
        f"Sitemap: {settings.SITE_URL}/sitemap.xml\n",
        content_type="text/plain",
    )


def health(request):
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse({"status": "ok", "service": "voltiq-storefront"})
    except Exception:
        return JsonResponse({"status": "degraded"}, status=503)


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
def error_400(request, exception=None):
    return render(request, "errors/400.html", status=400)


def error_403(request, exception=None):
    return render(request, "errors/403.html", status=403)


def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)


def csrf_failure(request, reason=""):
    return render(request, "errors/403.html", {"csrf_reason": reason}, status=403)
