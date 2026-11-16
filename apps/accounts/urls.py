from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("verify-email/", views.verify_pending, name="verify_pending"),
    path("verify-email/resend/", views.resend_verification, name="resend_verification"),
    path("verify-email/<str:token>/", views.verify_email, name="verify_email"),
    path("password-reset/", views.AccountPasswordResetView.as_view(), name="password_reset"),
    path("password-reset/sent/", views.AccountPasswordResetDoneView.as_view(), name="password_reset_done"),
    path(
        "password-reset/<uidb64>/<token>/",
        views.AccountPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        views.AccountPasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path("account/", views.dashboard, name="dashboard"),
    path("account/profile/", views.profile, name="profile"),
    path("account/password/", views.AccountPasswordChangeView.as_view(), name="password_change"),
    path("account/addresses/", views.address_list, name="addresses"),
    path("account/addresses/add/", views.address_create, name="address_create"),
    path("account/addresses/<int:pk>/edit/", views.address_edit, name="address_edit"),
    path("account/addresses/<int:pk>/delete/", views.address_delete, name="address_delete"),
    path("account/addresses/<int:pk>/default/", views.address_set_default, name="address_set_default"),
    path("account/notifications/", views.notifications, name="notifications"),
    path("account/notifications/read-all/", views.notifications_read_all, name="notifications_read_all"),
    path("account/payments/", views.payment_history, name="payments"),
]
