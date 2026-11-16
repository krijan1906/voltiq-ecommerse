from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cart.models import Cart, CartItem
from apps.core.testing import DEFAULT_PASSWORD, make_product, make_user
from apps.orders.models import Coupon


class CartServiceTests(TestCase):
    def setUp(self):
        self.product = make_product(price=Decimal("1000.00"), stock=5)

    def _guest_cart(self):
        return Cart.objects.filter(user__isnull=True).first()

    def test_add_to_cart_for_guest_creates_session_cart(self):
        response = self.client.post(
            reverse("cart:add"), {"product_id": self.product.pk, "quantity": 2}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["cart_count"], 2)
        cart = self._guest_cart()
        self.assertIsNotNone(cart)
        self.assertEqual(cart.items.get(product=self.product).quantity, 2)

    def test_add_rejects_quantity_above_stock(self):
        response = self.client.post(
            reverse("cart:add"), {"product_id": self.product.pk, "quantity": 6}
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertIn("Only 5", response.json()["message"])

    def test_add_rejects_inactive_or_out_of_stock_product(self):
        out_of_stock = make_product(stock=0)
        response = self.client.post(
            reverse("cart:add"), {"product_id": out_of_stock.pk, "quantity": 1}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["ok"], False)

    def test_add_accumulates_quantity_and_enforces_limit(self):
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk, "quantity": 3})
        response = self.client.post(
            reverse("cart:add"), {"product_id": self.product.pk, "quantity": 3}
        )
        self.assertEqual(response.status_code, 400)
        cart = self._guest_cart()
        self.assertEqual(cart.items.get(product=self.product).quantity, 3)

    def test_update_and_remove_item(self):
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk, "quantity": 2})
        item = self._guest_cart().items.get(product=self.product)
        response = self.client.post(reverse("cart:update", args=[item.pk]), {"quantity": 4})
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 4)

        response = self.client.post(reverse("cart:remove", args=[item.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertFalse(CartItem.objects.filter(pk=item.pk).exists())

    def test_setting_quantity_to_zero_removes_item(self):
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk, "quantity": 2})
        item = self._guest_cart().items.get(product=self.product)
        response = self.client.post(reverse("cart:update", args=[item.pk]), {"quantity": 0})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CartItem.objects.filter(pk=item.pk).exists())

    def test_coupon_applies_discount(self):
        coupon = Coupon.objects.create(
            code="SAVE10",
            discount_type=Coupon.DiscountType.PERCENTAGE,
            value=Decimal("10.00"),
            minimum_order_amount=Decimal("0.00"),
            valid_from=timezone.now() - timezone.timedelta(days=1),
        )
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk, "quantity": 1})
        response = self.client.post(reverse("cart:apply_coupon"), {"code": "save10"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["coupon"], coupon.code)
        self.assertEqual(data["discount_display"], "Rs. 100")
        self.assertEqual(data["total_display"], "Rs. 1,150")

    def test_invalid_and_below_minimum_coupons_are_rejected(self):
        Coupon.objects.create(
            code="BIGSPEND",
            discount_type=Coupon.DiscountType.FIXED,
            value=Decimal("500.00"),
            minimum_order_amount=Decimal("5000.00"),
            valid_from=timezone.now() - timezone.timedelta(days=1),
        )
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk, "quantity": 1})
        invalid = self.client.post(reverse("cart:apply_coupon"), {"code": "NOPE"})
        self.assertEqual(invalid.status_code, 400)

        below_minimum = self.client.post(reverse("cart:apply_coupon"), {"code": "BIGSPEND"})
        self.assertEqual(below_minimum.status_code, 400)
        self.assertIn("minimum", below_minimum.json()["message"].lower())

    def test_guest_cart_is_merged_on_login(self):
        user = make_user(email="merge@example.com")
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk, "quantity": 2})
        guest_cart = self._guest_cart()
        self.assertIsNotNone(guest_cart)

        self.assertTrue(self.client.login(email=user.email, password=DEFAULT_PASSWORD))
        user_cart = Cart.objects.get(user=user)
        self.assertEqual(user_cart.items.get(product=self.product).quantity, 2)
        self.assertFalse(Cart.objects.filter(pk=guest_cart.pk).exists())

    def test_cart_page_renders_with_conflicts(self):
        self.client.post(reverse("cart:add"), {"product_id": self.product.pk, "quantity": 2})
        response = self.client.get(reverse("cart:detail"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)

    def test_cart_summary_endpoint(self):
        response = self.client.get(reverse("cart:summary"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["cart_count"], 0)
