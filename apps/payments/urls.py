from django.urls import path

from apps.payments import views

app_name = "payments"

urlpatterns = [
    path("esewa/callback/", views.esewa_callback, name="esewa_callback"),
    path("khalti/callback/", views.khalti_callback, name="khalti_callback"),
    path("simulate/<str:transaction_ref>/", views.simulate, name="simulate"),
    path("failure/<str:order_number>/", views.failure, name="failure"),
    path("bank/<str:transaction_ref>/", views.bank_instructions, name="bank_instructions"),
]
