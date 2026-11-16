from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Notification
from apps.core.testing import make_order, make_product, make_user
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentTransaction
from apps.payments.services import simulate_payment, start_payment


class PaymentModelTests(TestCase):
    def setUp(self):
        self.user = make_user(email="payments@example.com")
        self.product = make_product(price=Decimal("2500.00"))
        self.order = make_order(user=self.user, product=self.product, payment_method=Order.PaymentMethod.ESEWA)

    def _payment(self, **kwargs):
        defaults = {
            "order": self.order,
            "gateway": Payment.Gateway.ESEWA,
            "amount": self.order.total,
            "status": Payment.Status.PENDING,
        }
        defaults.update(kwargs)
        return Payment.objects.create(**defaults)

    def test_mark_success_marks_order_paid_and_confirms_it(self):
        payment = self._payment()
        changed = payment.mark_success(payload={"verified": True}, gateway_ref="GW-123")
        self.assertTrue(changed)
        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertTrue(payment.is_verified)
        self.assertEqual(payment.gateway_ref, "GW-123")
        self.assertIsNotNone(payment.completed_at)
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)
        self.assertIsNotNone(self.order.confirmed_at)
        self.assertTrue(
            Notification.objects.filter(user=self.user, kind=Notification.Kind.PAYMENT).exists()
        )

    def test_mark_success_is_idempotent(self):
        payment = self._payment()
        self.assertTrue(payment.mark_success())
        self.assertFalse(payment.mark_success())

    def test_mark_failed_records_reason_and_order_state(self):
        payment = self._payment()
        changed = payment.mark_failed("Gateway declined", payload={"code": "DECLINED"})
        self.assertTrue(changed)
        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(payment.failed_reason, "Gateway declined")
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.FAILED)
        self.assertFalse(payment.mark_failed("again"))

    def test_only_one_successful_payment_per_order(self):
        first = self._payment()
        second = self._payment(status=Payment.Status.PENDING)
        first.mark_success()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                second.mark_success()

    def test_is_expired_after_timeout(self):
        payment = self._payment()
        Payment.objects.filter(pk=payment.pk).update(
            initiated_at=timezone.now() - timezone.timedelta(hours=2)
        )
        payment.refresh_from_db()
        self.assertTrue(payment.is_expired)


@override_settings(PAYMENT_SIMULATION=True, DEBUG=True)
class PaymentFlowTests(TestCase):
    def setUp(self):
        self.user = make_user(email="simulate@example.com")
        self.product = make_product(price=Decimal("3000.00"), stock=5)
        self.order = make_order(
            user=self.user, product=self.product, payment_method=Order.PaymentMethod.ESEWA
        )
        self.payment = Payment.objects.create(
            order=self.order,
            gateway=Payment.Gateway.ESEWA,
            amount=self.order.total,
            status=Payment.Status.PENDING,
        )

    def test_simulator_marks_payment_successful(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("payments:simulate", args=[self.payment.transaction_ref]),
            {"outcome": "success"},
        )
        self.assertEqual(response.status_code, 302)
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.SUCCESS)
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertTrue(
            self.payment.transactions.filter(event=PaymentTransaction.Event.SUCCEEDED).exists()
        )

    def test_simulator_can_record_failure(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("payments:simulate", args=[self.payment.transaction_ref]),
            {"outcome": "failure"},
        )
        self.assertEqual(response.status_code, 302)
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.FAILED)
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.FAILED)

    def test_simulator_is_hidden_when_disabled(self):
        with override_settings(PAYMENT_SIMULATION=False):
            self.client.force_login(self.user)
            response = self.client.get(reverse("payments:simulate", args=[self.payment.transaction_ref]))
            self.assertEqual(response.status_code, 404)

    def test_customer_cannot_simulate_another_customers_payment(self):
        stranger = make_user(email="stranger@example.com")
        self.client.force_login(stranger)
        response = self.client.get(reverse("payments:simulate", args=[self.payment.transaction_ref]))
        self.assertEqual(response.status_code, 404)

    def test_bank_instructions_render_for_owner(self):
        bank_payment = Payment.objects.create(
            order=self.order,
            gateway=Payment.Gateway.BANK,
            amount=self.order.total,
            status=Payment.Status.PENDING,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("payments:bank_instructions", args=[bank_payment.transaction_ref]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.order_number)

    def test_bank_instructions_are_private(self):
        bank_payment = Payment.objects.create(
            order=self.order,
            gateway=Payment.Gateway.BANK,
            amount=self.order.total,
            status=Payment.Status.PENDING,
        )
        stranger = make_user(email="bank-stranger@example.com")
        self.client.force_login(stranger)
        response = self.client.get(reverse("payments:bank_instructions", args=[bank_payment.transaction_ref]))
        self.assertEqual(response.status_code, 404)


@override_settings(PAYMENT_SIMULATION=True)
class StartPaymentTests(TestCase):
    def setUp(self):
        self.user = make_user(email="start@example.com")
        self.product = make_product(price=Decimal("1200.00"))
        self.order = make_order(user=self.user, product=self.product)

    def test_online_payment_without_credentials_uses_simulator(self):
        request = self.client.get(reverse("core:home")).wsgi_request
        payment, initiation = start_payment(self.order, "esewa", request)
        self.assertIsNotNone(payment)
        self.assertEqual(payment.gateway, Payment.Gateway.ESEWA)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.gateway_ref, "SIMULATED")
        self.assertIn("simulate", initiation.redirect_url)
        self.assertTrue(
            payment.transactions.filter(status="simulated").exists()
        )

    def test_new_attempt_expires_previous_pending_payment(self):
        request = self.client.get(reverse("core:home")).wsgi_request
        first, _ = start_payment(self.order, "esewa", request)
        second, _ = start_payment(self.order, "esewa", request)
        first.refresh_from_db()
        self.assertEqual(first.status, Payment.Status.EXPIRED)
        self.assertEqual(second.attempt_number, 2)

    def test_paid_order_cannot_start_another_payment(self):
        request = self.client.get(reverse("core:home")).wsgi_request
        payment, _ = start_payment(self.order, "esewa", request)
        payment.mark_success()
        returned, initiation = start_payment(self.order, "esewa", request)
        self.assertIsNone(returned)
        self.assertIn("already paid", initiation.message.lower())
