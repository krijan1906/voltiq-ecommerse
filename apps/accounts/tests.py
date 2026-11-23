from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.forms import RegisterForm
from apps.accounts.models import Address, CustomerProfile, EmailVerificationToken, Notification, User
from apps.core.testing import DEFAULT_PASSWORD, make_address, make_order, make_product, make_user

STRONG_PASSWORD = "VoltiqTest!2026"


class RegistrationTests(TestCase):
    def _payload(self, **overrides):
        data = {
            "first_name": "Nabin",
            "last_name": "Karki",
            "email": "nabin@example.com",
            "phone": "+977 980-123-4567",
            "password1": STRONG_PASSWORD,
            "password2": STRONG_PASSWORD,
            "terms": "on",
            "newsletter": "on",
        }
        data.update(overrides)
        return data

    def test_registration_creates_unverified_user_and_token(self):
        response = self.client.post(reverse("accounts:register"), self._payload())
        self.assertRedirects(response, reverse("accounts:verify_pending"))
        user = User.objects.get(email="nabin@example.com")
        self.assertFalse(user.is_email_verified)
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertTrue(user.newsletter_opt_in)
        self.assertTrue(CustomerProfile.objects.filter(user=user).exists())
        self.assertTrue(EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).exists())
        self.assertTrue(len(mail.outbox) >= 1)

    def test_registration_rejects_duplicate_email(self):
        make_user(email="duplicate@example.com")
        response = self.client.post(
            reverse("accounts:register"), self._payload(email="duplicate@example.com")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")

    def test_duplicate_insert_race_reports_form_error(self):
        # Simulate the window where two submissions both pass the duplicate
        # check: the database constraint must produce a form error, not a 500.
        make_user(email="race@example.com")
        with patch.object(RegisterForm, "clean_email", lambda self: self.cleaned_data["email"].lower()):
            response = self.client.post(
                reverse("accounts:register"), self._payload(email="race@example.com")
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertEqual(User.objects.filter(email="race@example.com").count(), 1)

    def test_registration_rejects_terms_not_accepted(self):
        response = self.client.post(reverse("accounts:register"), self._payload(terms=""))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="nabin@example.com").exists())

    def test_verification_token_marks_email_verified(self):
        self.client.post(reverse("accounts:register"), self._payload())
        user = User.objects.get(email="nabin@example.com")
        token = EmailVerificationToken.objects.get(user=user)
        response = self.client.get(reverse("accounts:verify_email", args=[token.token]))
        self.assertRedirects(response, reverse("accounts:dashboard"))
        user.refresh_from_db()
        token.refresh_from_db()
        self.assertTrue(user.is_email_verified)
        self.assertIsNotNone(user.email_verified_at)
        self.assertIsNotNone(token.used_at)

    def test_verification_email_contains_direct_link(self):
        self.client.post(reverse("accounts:register"), self._payload())
        user = User.objects.get(email="nabin@example.com")
        token = EmailVerificationToken.objects.get(user=user, used_at__isnull=True)
        body = "\n".join(message.body for message in mail.outbox)
        self.assertIn(f"/accounts/verify-email/{token.token}/", body)
        self.assertNotIn("Verification%20for", body)
        response = self.client.get(reverse("accounts:verify_email", args=[token.token]))
        self.assertRedirects(response, reverse("accounts:dashboard"))
        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)

    def test_expired_verification_token_is_rejected(self):
        user = make_user(email="expired@example.com", verified=False)
        token = EmailVerificationToken.objects.create(
            user=user, token="expired-token", expires_at=timezone.now() - timezone.timedelta(hours=1)
        )
        response = self.client.get(reverse("accounts:verify_email", args=[token.token]))
        self.assertRedirects(response, reverse("accounts:login"))
        user.refresh_from_db()
        self.assertFalse(user.is_email_verified)


class LoginTests(TestCase):
    def setUp(self):
        self.user = make_user(email="login@example.com", first_name="Login")

    def test_login_with_email_succeeds(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": self.user.email, "password": DEFAULT_PASSWORD},
        )
        self.assertRedirects(response, reverse("accounts:dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_with_wrong_password_fails(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": self.user.email, "password": "wrong-password"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_suspended_user_cannot_log_in(self):
        User.objects.filter(pk=self.user.pk).update(is_suspended=True, suspension_reason="Fraud review")
        response = self.client.post(
            reverse("accounts:login"),
            {"username": self.user.email, "password": DEFAULT_PASSWORD},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "suspended")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class AccountAreaTests(TestCase):
    def setUp(self):
        self.user = make_user(email="account@example.com", first_name="Asha", last_name="Rai")
        self.client.force_login(self.user)

    def test_dashboard_shows_order_summary(self):
        product = make_product()
        order = make_order(user=self.user, product=product)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.order_number)
        self.assertEqual(response.context["order_count"], 1)

    def test_profile_update(self):
        response = self.client.post(
            reverse("accounts:profile"),
            {
                "first_name": "Asha",
                "last_name": "Shrestha",
                "phone": "+977 981-222-3333",
                "newsletter_opt_in": "on",
            },
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, "Shrestha")
        self.assertTrue(self.user.newsletter_opt_in)

    def test_address_create_and_list(self):
        response = self.client.post(
            reverse("accounts:address_create"),
            {
                "label": "Office",
                "full_name": "Asha Rai",
                "phone": "+977 980-111-2222",
                "street_address": "Ward 4, Lazimpat",
                "city": "Kathmandu",
                "district": "Kathmandu",
                "province": "bagmati",
                "postal_code": "44600",
                "country": "Nepal",
                "address_type": "both",
            },
        )
        self.assertRedirects(response, reverse("accounts:addresses"))
        address = Address.objects.get(user=self.user)
        self.assertEqual(address.label, "Office")
        self.assertTrue(address.is_default)

        listing = self.client.get(reverse("accounts:addresses"))
        self.assertContains(listing, "Ward 4, Lazimpat")

    def test_address_delete_is_scoped_to_owner(self):
        other = make_user(email="address-other@example.com")
        address = make_address(other)
        response = self.client.post(reverse("accounts:address_delete", args=[address.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Address.objects.filter(pk=address.pk).exists())

    def test_setting_default_address_unsets_previous_default(self):
        first = make_address(self.user, label="Home")
        second = Address.objects.create(
            user=self.user,
            label="Work",
            full_name="Asha Rai",
            phone="+977 980-111-2222",
            street_address="Office Road",
            city="Kathmandu",
            district="Kathmandu",
            province="bagmati",
            country="Nepal",
        )
        self.client.post(reverse("accounts:address_set_default", args=[second.pk]))
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)

    def test_notifications_can_be_marked_read(self):
        Notification.push(self.user, "Test notification", "Something happened.")
        response = self.client.post(reverse("accounts:notifications_read_all"))
        self.assertRedirects(response, reverse("accounts:notifications"))
        self.assertFalse(self.user.notifications.filter(is_read=False).exists())

    def test_payment_history_only_shows_own_payments(self):
        from apps.payments.models import Payment

        product = make_product()
        order = make_order(user=self.user, product=product)
        Payment.objects.create(order=order, gateway=Payment.Gateway.COD, amount=order.total)
        response = self.client.get(reverse("accounts:payments"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.order_number)


class PasswordTests(TestCase):
    def setUp(self):
        self.user = make_user(email="password@example.com")

    def test_password_reset_sends_email(self):
        response = self.client.post(reverse("accounts:password_reset"), {"email": self.user.email})
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("password", mail.outbox[0].subject.lower())

    def test_password_change(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": DEFAULT_PASSWORD,
                "new_password1": STRONG_PASSWORD,
                "new_password2": STRONG_PASSWORD,
            },
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(STRONG_PASSWORD))
