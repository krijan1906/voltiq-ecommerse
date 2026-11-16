from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import Notification
from apps.core.testing import make_order, make_product, make_staff, make_user
from apps.inventory.models import StockHistory
from apps.inventory.services import StockError, adjust_stock, restock_order, set_stock
from apps.wishlist.models import Wishlist, WishlistItem


class StockAdjustmentTests(TestCase):
    def setUp(self):
        self.staff = make_staff(email="stock@example.com")
        self.product = make_product(stock=10)

    def test_positive_adjustment_records_history(self):
        adjust_stock(
            self.product,
            5,
            StockHistory.Reason.RESTOCK,
            reference="PO-1001",
            user=self.staff,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 15)
        history = StockHistory.objects.get(product=self.product)
        self.assertEqual(history.change, 5)
        self.assertEqual(history.previous_quantity, 10)
        self.assertEqual(history.new_quantity, 15)
        self.assertEqual(history.reason, StockHistory.Reason.RESTOCK)
        self.assertEqual(history.reference, "PO-1001")
        self.assertEqual(history.changed_by, self.staff)

    def test_negative_adjustment_cannot_take_stock_below_zero(self):
        with self.assertRaises(StockError):
            adjust_stock(self.product, -11, StockHistory.Reason.DAMAGE)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertFalse(StockHistory.objects.exists())

    def test_negative_adjustment_within_stock(self):
        adjust_stock(self.product, -4, StockHistory.Reason.DAMAGE)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 6)
        self.assertEqual(
            StockHistory.objects.get(product=self.product).new_quantity, 6
        )

    def test_set_stock_to_same_quantity_is_a_noop(self):
        result = set_stock(self.product, 10)
        self.assertEqual(result.stock_quantity, 10)
        self.assertFalse(StockHistory.objects.exists())

    def test_set_stock_creates_adjustment(self):
        set_stock(self.product, 42, reference="Stock count")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 42)
        history = StockHistory.objects.get(product=self.product)
        self.assertEqual(history.change, 32)
        self.assertEqual(history.reason, StockHistory.Reason.ADJUSTMENT)

    def test_restock_order_adds_every_item_back(self):
        user = make_user(email="restock-order@example.com")
        second = make_product(stock=3)
        order = make_order(user=user, product=self.product, quantity=2)
        order.items.create(
            order=order,
            product=second,
            product_name=second.name,
            sku=second.sku,
            unit_price=second.current_price,
            quantity=1,
        )
        # Pretend the sale already deducted stock.
        self.product.stock_quantity = 8
        self.product.save(update_fields=["stock_quantity"])
        second.stock_quantity = 2
        second.save(update_fields=["stock_quantity"])

        restock_order(order, changed_by=self.staff)
        self.product.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(second.stock_quantity, 3)
        self.assertEqual(
            StockHistory.objects.filter(order=order, reason=StockHistory.Reason.CANCELLATION).count(), 2
        )

    def test_restock_notifies_wishlist_subscribers(self):
        user = make_user(email="restock-notify@example.com")
        product = make_product(stock=0)
        wishlist = Wishlist.objects.create(user=user)
        WishlistItem.objects.create(wishlist=wishlist, product=product, notify_on_restock=True)

        adjust_stock(product, 3, StockHistory.Reason.RESTOCK)
        self.assertTrue(
            Notification.objects.filter(user=user, kind=Notification.Kind.WISHLIST).exists()
        )

    def test_restock_does_not_notify_when_stock_was_already_positive(self):
        user = make_user(email="restock-silent@example.com")
        product = make_product(stock=2)
        wishlist = Wishlist.objects.create(user=user)
        WishlistItem.objects.create(wishlist=wishlist, product=product, notify_on_restock=True)
        adjust_stock(product, 3, StockHistory.Reason.RESTOCK)
        self.assertFalse(Notification.objects.filter(user=user).exists())
