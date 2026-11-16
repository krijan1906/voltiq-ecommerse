from django.urls import path

from apps.dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.overview, name="overview"),
    # Products
    path("products/", views.product_list, name="product_list"),
    path("products/add/", views.product_create, name="product_create"),
    path("products/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("products/<int:pk>/delete/", views.product_delete, name="product_delete"),
    path("products/<int:pk>/toggle/", views.product_toggle, name="product_toggle"),
    path("products/<int:pk>/images/upload/", views.product_image_upload, name="product_image_upload"),
    path("products/<int:pk>/images/<int:image_id>/delete/", views.product_image_delete, name="product_image_delete"),
    path("products/<int:pk>/images/<int:image_id>/primary/", views.product_image_primary, name="product_image_primary"),
    path("api/category-specs/<int:pk>/", views.category_specs_api, name="category_specs_api"),
    # Catalogue structure
    path("categories/", views.category_list, name="category_list"),
    path("categories/add/", views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category_edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("brands/", views.brand_list, name="brand_list"),
    path("brands/add/", views.brand_create, name="brand_create"),
    path("brands/<int:pk>/edit/", views.brand_edit, name="brand_edit"),
    path("brands/<int:pk>/delete/", views.brand_delete, name="brand_delete"),
    path("spec-fields/", views.specfield_list, name="specfield_list"),
    path("spec-fields/add/", views.specfield_create, name="specfield_create"),
    path("spec-fields/<int:pk>/edit/", views.specfield_edit, name="specfield_edit"),
    path("spec-fields/<int:pk>/delete/", views.specfield_delete, name="specfield_delete"),
    # Orders
    path("orders/", views.order_list, name="order_list"),
    path("orders/<str:order_number>/", views.order_detail, name="order_detail"),
    path("orders/<str:order_number>/status/", views.order_update_status, name="order_update_status"),
    path("orders/<str:order_number>/mark-paid/", views.order_mark_paid, name="order_mark_paid"),
    path("orders/<str:order_number>/invoice.pdf", views.order_invoice, name="order_invoice"),
    # Customers
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    path("customers/<int:pk>/suspend/", views.customer_toggle_suspension, name="customer_toggle_suspension"),
    path("customers/<int:pk>/role/", views.customer_set_role, name="customer_set_role"),
    # Inventory
    path("inventory/", views.inventory_list, name="inventory_list"),
    path("inventory/<int:pk>/adjust/", views.inventory_adjust, name="inventory_adjust"),
    path("inventory/history/", views.stock_history, name="stock_history"),
    # Reports
    path("reports/", views.reports, name="reports"),
    path("reports/orders.csv", views.export_orders_csv, name="export_orders_csv"),
    path("reports/newsletter.csv", views.export_newsletter_csv, name="export_newsletter_csv"),
    # Reviews / coupons / marketing / messages
    path("reviews/", views.review_list, name="review_list"),
    path("reviews/<int:pk>/toggle/", views.review_toggle, name="review_toggle"),
    path("reviews/<int:pk>/delete/", views.review_delete, name="review_delete"),
    path("coupons/", views.coupon_list, name="coupon_list"),
    path("coupons/add/", views.coupon_create, name="coupon_create"),
    path("coupons/<int:pk>/edit/", views.coupon_edit, name="coupon_edit"),
    path("coupons/<int:pk>/delete/", views.coupon_delete, name="coupon_delete"),
    path("newsletter/", views.newsletter_list, name="newsletter_list"),
    path("messages/", views.contact_messages, name="contact_messages"),
    path("messages/<int:pk>/status/", views.contact_message_status, name="contact_message_status"),
    # Settings
    path("settings/", views.store_settings, name="store_settings"),
    path("settings/shipping/<int:pk>/edit/", views.shipping_edit, name="shipping_edit"),
    path("settings/shipping/<int:pk>/delete/", views.shipping_delete, name="shipping_delete"),
]
