from django.urls import path

from apps.orders import views

app_name = "checkout"

urlpatterns = [
    path("", views.checkout_contact, name="contact"),
    path("address/", views.checkout_address, name="address"),
    path("shipping/", views.checkout_shipping, name="shipping"),
    path("review/", views.checkout_review, name="review"),
    path("payment/", views.checkout_payment, name="payment"),
]
