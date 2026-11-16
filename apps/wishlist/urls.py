from django.urls import path

from apps.wishlist import views

app_name = "wishlist"

urlpatterns = [
    path("", views.wishlist_detail, name="detail"),
    path("toggle/", views.toggle, name="toggle"),
    path("remove/<int:item_id>/", views.remove_item, name="remove"),
    path("move-to-cart/<int:item_id>/", views.move_to_cart, name="move_to_cart"),
]
