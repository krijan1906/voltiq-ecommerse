from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cart.models import Cart
from apps.cart.services import add_to_cart
from apps.core.testing import make_address, make_order, make_product, make_shipping, make_user
from apps.inventory.models import StockHistory
from apps.orders.models import Coupon, CouponUsage, Order, OrderItem
from apps.orders.services import CheckoutError, cancel_order, create_order_from_cart
from apps.products.models import Product


class CreateOrderTests(TestCase):
    def setUp(self):
        self.user = make_user(email="checkout@example.com")
        self.address = make_address(self.user)
        self.shipping = make_shipping(charge=Decimal("250.00"))
        self.product = make_product(price=Decimal("2000.00"), stock=10)

    def _cart_with(self, quantity=2):
        cart = Cart.objects.create(user=self.user)
        cart.items.create(product=self.product, quantity=quantity, price_snapshot=self.product.current_price)
        return cart

    def _contact(self):
        return {"full_name": "Test Buyer", "email": self.user.email, "phone": "+977 980-000-0000"}

    def test_order_created_and_stock_deducted(self):
        cart = self._cart_with(2)
        order = create_order_from_cart(
            cart,
            user=self.user,
            contact=self._contact(),
            shipping_address=self.address,
            shipping_method=self.shipping,
            payment_method=Order.PaymentMethod.COD,
        )
        self.assertIsInstance(order, Order)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.subtotal, Decimal("4000.00"))
        self.assertEqual(order.shipping_fee, Decimal("250.00"))
        self.assertEqual(order.total, Decimal("4250.00"))
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.status_history.count(), 1)
        self.assertEqual(order.status_history.first().status, Order.Status.PENDING)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 8)
        self.assertEqual(self.product.sales_count, 2)
        self.assertTrue(
            StockHistory.objects.filter(
                product=self.product,
                order=order,
                reason=StockHistory.Reason.SALE,
                change=-2,
                previous_quantity=10,
                new_quantity=8,
            ).exists()
        )

        cart.refresh_from_db()
        self.assertEqual(cart.items.count(), 0)
        self.assertIsNone(cart.coupon)

    def test_order_snapshots_product_price_and_details(self):
        cart = self._cart_with(1)
        order = create_order_from_cart(
            cart,
            user=self.user,
            contact=self._contact(),
            shipping_address=self.address,
            shipping_method=self.shipping,
            payment_method=Order.PaymentMethod.COD,
        )
        item = order.items.first()
        self.assertEqual(item.product_name, self.product.name)
        self.assertEqual(item.sku, self.product.sku)
        self.assertEqual(item.unit_price, Decimal("2000.00"))
        self.assertEqual(item.line_total, Decimal("2000.00"))

    def test_coupon_is_recorded_once(self):
        coupon = Coupon.objects.create(
            code="ORDER10",
            discount_type=Coupon.DiscountType.PERCENTAGE,
            value=Decimal("10.00"),
            minimum_order_amount=Decimal("0.00"),
            valid_from=timezone.now() - timezone.timedelta(days=1),
        )
        cart = self._cart_with(2)
        cart.coupon = coupon
        cart.save(update_fields=["coupon"])
        order = create_order_from_cart(
            cart,
            user=self.user,
            contact=self._contact(),
            shipping_address=self.address,
            shipping_method=self.shipping,
            payment_method=Order.PaymentMethod.COD,
        )
        self.assertEqual(order.discount_amount, Decimal("400.00"))
        self.assertEqual(order.total, Decimal("3850.00"))
        coupon.refresh_from_db()
        self.assertEqual(coupon.used_count, 1)
        self.assertTrue(CouponUsage.objects.filter(coupon=coupon, order=order).exists())

    def test_insufficient_stock_aborts_without_changes(self):
        cart = self._cart_with(20)
        with self.assertRaises(CheckoutError):
            create_order_from_cart(
                cart,
                user=self.user,
                contact=self._contact(),
                shipping_address=self.address,
                shipping_method=self.shipping,
                payment_method=Order.PaymentMethod.COD,
            )
        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(cart.items.count(), 1)

    def test_inactive_product_aborts(self):
        cart = self._cart_with(1)
        Product.objects.filter(pk=self.product.pk).update(is_active=False)
        with self.assertRaises(CheckoutError):
            create_order_from_cart(
                cart,
                user=self.user,
                contact=self._contact(),
                shipping_address=self.address,
                shipping_method=self.shipping,
                payment_method=Order.PaymentMethod.COD,
            )
        self.assertEqual(Order.objects.count(), 0)

    def test_empty_cart_raises(self):
        cart = Cart.objects.create(user=self.user)
        with self.assertRaises(CheckoutError):
            create_order_from_cart(
                cart,
                user=self.user,
                contact=self._contact(),
                shipping_address=self.address,
                shipping_method=self.shipping,
                payment_method=Order.PaymentMethod.COD,
            )


class CancelOrderTests(TestCase):
    def setUp(self):
        self.user = make_user(email="cancel@example.com")
        self.product = make_product(stock=5, price=Decimal("1500.00"))
        self.shipping = make_shipping()
        self.order = make_order(user=self.user, product=self.product, quantity=2, shipping_method=self.shipping)

    def test_cancel_order_restocks_and_records_history(self):
        # Simulate the initial sale so the restock can be observed.
        self.product.stock_quantity = 3
        self.product.save(update_fields=["stock_quantity"])
        cancel_order(self.order, changed_by=self.user, reason="Changed my mind")
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertIsNotNone(self.order.cancelled_at)
        self.assertEqual(self.product.stock_quantity, 5)
        self.assertTrue(
            self.order.status_history.filter(status=Order.Status.CANCELLED).exists()
        )
        self.assertTrue(
            StockHistory.objects.filter(order=self.order, reason=StockHistory.Reason.CANCELLATION).exists()
        )

    def test_delivered_order_cannot_be_cancelled(self):
        Order.objects.filter(pk=self.order.pk).update(status=Order.Status.DELIVERED)
        self.order.refresh_from_db()
        with self.assertRaises(CheckoutError):
            cancel_order(self.order, changed_by=self.user)


class CheckoutFlowTests(TestCase):
    def setUp(self):
        self.user = make_user(email="flow@example.com")
        self.address = make_address(self.user)
        self.product = make_product(price=Decimal("5000.00"), stock=10)
        self.shipping = make_shipping(code="standard", charge=Decimal("250.00"))
        cart = Cart.objects.create(user=self.user)
        cart.items.create(product=self.product, quantity=1, price_snapshot=self.product.current_price)

    def test_anonymous_checkout_redirects_to_login(self):
        response = self.client.get(reverse("checkout:contact"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_unverified_customer_is_sent_to_verification(self):
        unverified = make_user(email="unverified@example.com", verified=False)
        cart = Cart.objects.create(user=unverified)
        cart.items.create(product=self.product, quantity=1, price_snapshot=self.product.current_price)
        self.client.force_login(unverified)
        response = self.client.get(reverse("checkout:contact"))
        self.assertRedirects(response, reverse("accounts:verify_pending"))

    def test_empty_cart_redirects(self):
        empty = make_user(email="empty@example.com")
        self.client.force_login(empty)
        response = self.client.get(reverse("checkout:contact"))
        self.assertRedirects(response, reverse("cart:detail"))

    def test_full_checkout_with_cash_on_delivery(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("checkout:contact"))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("checkout:contact"),
            {"full_name": "Flow Tester", "email": self.user.email, "phone": "+977 980-111-2222"},
        )
        self.assertRedirects(response, reverse("checkout:address"))

        response = self.client.post(
            reverse("checkout:address"),
            {"form_type": "existing", "address_id": self.address.pk},
        )
        self.assertRedirects(response, reverse("checkout:shipping"))

        response = self.client.post(
            reverse("checkout:shipping"), {"shipping_method": self.shipping.pk}
        )
        self.assertRedirects(response, reverse("checkout:review"))

        response = self.client.get(reverse("checkout:review"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client.session["checkout"]["reviewed"])

        response = self.client.get(reverse("checkout:payment"))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("checkout:payment"), {"payment_method": "cod", "customer_notes": "Call first"}
        )
        self.assertEqual(response.status_code, 302)

        order = Order.objects.get(user=self.user)
        self.assertEqual(order.payment_method, Order.PaymentMethod.COD)
        self.assertEqual(order.customer_notes, "Call first")
        self.assertEqual(order.shipping_method, self.shipping)
        self.assertEqual(order.items.get().product, self.product)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 9)
        self.assertNotIn("checkout", self.client.session)

    def test_payment_step_requires_review(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse("checkout:contact"),
            {"full_name": "Flow Tester", "email": self.user.email, "phone": "+977 980-111-2222"},
        )
        self.client.post(
            reverse("checkout:address"), {"form_type": "existing", "address_id": self.address.pk}
        )
        self.client.post(reverse("checkout:shipping"), {"shipping_method": self.shipping.pk})
        # Skip the review step.
        response = self.client.get(reverse("checkout:payment"))
        self.assertRedirects(response, reverse("checkout:review"))


class OrderViewTests(TestCase):
    def setUp(self):
        self.user = make_user(email="orders@example.com")
        self.other = make_user(email="other@example.com")
        self.product = make_product()
        self.order = make_order(user=self.user, product=self.product)

    def test_order_list_requires_login(self):
        response = self.client.get(reverse("orders:list"))
        self.assertEqual(response.status_code, 302)

    def test_customer_sees_only_their_orders(self):
        make_order(user=self.other, product=self.product)
        self.client.force_login(self.user)
        response = self.client.get(reverse("orders:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.order_number)
        self.assertEqual(len(response.context["orders"]), 1)

    def test_order_detail_is_owner_only(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("orders:detail", args=[self.order.order_number]))
        self.assertEqual(response.status_code, 302)

    def test_owner_can_download_pdf_invoice(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("orders:invoice", args=[self.order.order_number]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_other_customer_cannot_download_invoice(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("orders:invoice", args=[self.order.order_number]))
        self.assertRedirects(response, reverse("orders:list"))

    def test_cancel_endpoint_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("orders:cancel", args=[self.order.order_number]))
        self.assertEqual(response.status_code, 405)

    def test_reorder_adds_items_to_cart(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("orders:reorder", args=[self.order.order_number]))
        self.assertEqual(response.status_code, 302)
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.get(product=self.product).quantity, 1)
