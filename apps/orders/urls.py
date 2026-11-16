from django.urls import path

from apps.orders import views

app_name = "orders"

urlpatterns = [
    path("", views.order_list, name="list"),
    path("<str:order_number>/confirmation/", views.confirmation, name="confirmation"),
    path("<str:order_number>/track/", views.order_track, name="track"),
    path("<str:order_number>/cancel/", views.order_cancel, name="cancel"),
    path("<str:order_number>/reorder/", views.order_reorder, name="reorder"),
    path("<str:order_number>/payment/", views.order_payment, name="payment"),
    path("<str:order_number>/invoice.pdf", views.invoice_pdf, name="invoice"),
    path("<str:order_number>/", views.order_detail, name="detail"),
]
