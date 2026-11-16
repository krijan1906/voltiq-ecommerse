from django.urls import path

from apps.products import views

app_name = "products"

urlpatterns = [
    path("", views.product_list, name="list"),
    path("search/suggestions/", views.search_suggestions, name="suggestions"),
    path("<slug:slug>/", views.product_detail, name="detail"),
]
