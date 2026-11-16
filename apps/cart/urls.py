from django.urls import path

from apps.cart import views

app_name = "cart"

urlpatterns = [
    path("", views.cart_detail, name="detail"),
    path("add/", views.add_item, name="add"),
    path("update/<int:item_id>/", views.update_item, name="update"),
    path("remove/<int:item_id>/", views.remove_item, name="remove"),
    path("coupon/apply/", views.apply_coupon_view, name="apply_coupon"),
    path("coupon/remove/", views.remove_coupon_view, name="remove_coupon"),
    path("summary/", views.cart_summary, name="summary"),
]
