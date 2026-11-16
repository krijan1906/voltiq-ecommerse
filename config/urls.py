from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("apps.core.urls", namespace="core")),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("products/", include("apps.products.urls", namespace="products")),
    path("cart/", include("apps.cart.urls", namespace="cart")),
    path("wishlist/", include("apps.wishlist.urls", namespace="wishlist")),
    path("checkout/", include("apps.orders.checkout_urls", namespace="checkout")),
    path("orders/", include("apps.orders.urls", namespace="orders")),
    path("payments/", include("apps.payments.urls", namespace="payments")),
    path("reviews/", include("apps.reviews.urls", namespace="reviews")),
    path("dashboard/", include("apps.dashboard.urls", namespace="dashboard")),
]

CSRF_FAILURE_VIEW = "apps.core.views.csrf_failure"

handler400 = "apps.core.views.error_400"
handler403 = "apps.core.views.error_403"
handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"
CSRF_FAILURE_VIEW = "apps.core.views.csrf_failure"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
