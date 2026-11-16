from django.urls import path

from apps.core import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("newsletter/subscribe/", views.newsletter_subscribe, name="newsletter_subscribe"),
    path("newsletter/unsubscribe/<str:token>/", views.newsletter_unsubscribe, name="newsletter_unsubscribe"),
    path("contact/", views.contact, name="contact"),
    path("about/", views.about, name="about"),
    path("faq/", views.faq, name="faq"),
    path("privacy/", views.policy, {"slug": "privacy"}, name="privacy"),
    path("terms/", views.policy, {"slug": "terms"}, name="terms"),
    path("shipping/", views.policy, {"slug": "shipping"}, name="shipping"),
    path("returns/", views.policy, {"slug": "returns"}, name="returns"),
    path("robots.txt", views.robots_txt, name="robots"),
    path("health/", views.health, name="health"),
]
