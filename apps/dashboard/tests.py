from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Notification, User
from apps.categories.models import Brand, Category
from apps.core.models import ContactMessage, NewsletterSubscription
from apps.core.testing import make_order, make_product, make_shipping, make_staff, make_user
from apps.inventory.models import StockHistory
from apps.orders.models import Coupon, Order
from apps.products.models import Product
from apps.reviews.models import Review


class DashboardAccessTests(TestCase):
    def setUp(self):
        self.customer = make_user(email="dash-customer@example.com")
        self.staff = make_staff(email="dash-staff@example.com")
        self.admin = make_staff(email="dash-admin@example.com", admin=True)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse("dashboard:overview"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_customer_is_forbidden(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("dashboard:overview"))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_open_dashboard(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("dashboard:overview"))
        self.assertEqual(response.status_code, 200)

    def test_only_administrators_can_open_settings(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("dashboard:store_settings")).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("dashboard:store_settings")).status_code, 200)


class DashboardPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_staff(email="pages-admin@example.com", admin=True)
        cls.product = make_product(name="Dashboard Product", stock=4)
        cls.customer = make_user(email="page-customer@example.com", first_name="Page")
        cls.order = make_order(user=cls.customer, product=cls.product)
        cls.review = Review.objects.create(
            product=cls.product,
            user=cls.customer,
            rating=5,
            title="Great",
            body="A detailed and helpful review body.",
        )
        cls.coupon = Coupon.objects.create(
            code="PAGE10",
            discount_type=Coupon.DiscountType.PERCENTAGE,
            value=Decimal("10.00"),
            valid_from=timezone.now() - timezone.timedelta(days=1),
        )
        cls.category = make_category = Category.objects.create(name="Inventory Category")
        cls.brand = Brand.objects.create(name="Inventory Brand")
        NewsletterSubscription.objects.create(email="subscriber@example.com", token="sub-token")
        ContactMessage.objects.create(
            name="Customer",
            email="contact@example.com",
            subject="Help",
            message="I need help with my order please.",
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_all_dashboard_pages_render(self):
        pages = [
            reverse("dashboard:overview"),
            reverse("dashboard:product_list"),
            reverse("dashboard:product_create"),
            reverse("dashboard:product_edit", args=[self.product.pk]),
            reverse("dashboard:category_list"),
            reverse("dashboard:category_create"),
            reverse("dashboard:brand_list"),
            reverse("dashboard:brand_create"),
            reverse("dashboard:specfield_list"),
            reverse("dashboard:order_list"),
            reverse("dashboard:order_detail", args=[self.order.order_number]),
            reverse("dashboard:customer_list"),
            reverse("dashboard:customer_detail", args=[self.customer.pk]),
            reverse("dashboard:inventory_list"),
            reverse("dashboard:inventory_adjust", args=[self.product.pk]),
            reverse("dashboard:stock_history"),
            reverse("dashboard:reports"),
            reverse("dashboard:review_list"),
            reverse("dashboard:coupon_list"),
            reverse("dashboard:coupon_create"),
            reverse("dashboard:coupon_edit", args=[self.coupon.pk]),
            reverse("dashboard:newsletter_list"),
            reverse("dashboard:contact_messages"),
            reverse("dashboard:store_settings"),
        ]
        for url in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_dashboard_search_filters_products(self):
        make_product(name="Unrelated Thing")
        response = self.client.get(reverse("dashboard:product_list"), {"q": "Dashboard Product"})
        self.assertContains(response, "Dashboard Product")
        self.assertNotContains(response, "Unrelated Thing")

    def test_order_export_returns_csv(self):
        response = self.client.get(reverse("dashboard:export_orders_csv"))
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn(self.order.order_number, response.content.decode())

    def test_newsletter_export_returns_csv(self):
        response = self.client.get(reverse("dashboard:export_newsletter_csv"))
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("subscriber@example.com", response.content.decode())

    def test_reports_accepts_date_range(self):
        today = timezone.localdate()
        response = self.client.get(
            reverse("dashboard:reports"),
            {"start": today.isoformat(), "end": today.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("chart_labels", response.context)


class DashboardActionTests(TestCase):
    def setUp(self):
        self.admin = make_staff(email="actions-admin@example.com", admin=True)
        self.client.force_login(self.admin)
        self.product = make_product(stock=10, price=Decimal("1500.00"))
        self.customer = make_user(email="action-customer@example.com")
        self.order = make_order(user=self.customer, product=self.product)

    def test_product_toggle_deactivates_and_unfeatures(self):
        Product.objects.filter(pk=self.product.pk).update(is_featured=True)
        response = self.client.post(reverse("dashboard:product_toggle", args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)
        self.assertFalse(self.product.is_featured)

    def test_inventory_adjust_updates_stock_and_audit_trail(self):
        response = self.client.post(
            reverse("dashboard:inventory_adjust", args=[self.product.pk]),
            {
                "product_id": self.product.pk,
                "new_quantity": 25,
                "reason": StockHistory.Reason.RESTOCK,
                "reference": "Delivery note 42",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 25)
        history = StockHistory.objects.get(product=self.product)
        self.assertEqual(history.change, 15)
        self.assertEqual(history.changed_by, self.admin)
        self.assertEqual(history.reference, "Delivery note 42")

    def test_order_status_update_records_history_and_notifies(self):
        response = self.client.post(
            reverse("dashboard:order_update_status", args=[self.order.order_number]),
            {"status": Order.Status.PROCESSING, "note": "Packed", "courier": "Nepal Post"},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        self.assertEqual(self.order.courier, "Nepal Post")
        self.assertTrue(
            self.order.status_history.filter(status=Order.Status.PROCESSING).exists()
        )
        self.assertTrue(
            Notification.objects.filter(user=self.customer, kind=Notification.Kind.ORDER).exists()
        )

    def test_cancelling_order_through_dashboard_restocks(self):
        self.product.stock_quantity = 8
        self.product.save(update_fields=["stock_quantity"])
        response = self.client.post(
            reverse("dashboard:order_update_status", args=[self.order.order_number]),
            {"status": Order.Status.CANCELLED, "note": "Customer request"},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(self.product.stock_quantity, 9)

    def test_coupon_can_be_created(self):
        now = timezone.localtime()
        response = self.client.post(
            reverse("dashboard:coupon_create"),
            {
                "code": "newyear",
                "description": "New year offer",
                "discount_type": Coupon.DiscountType.FIXED,
                "value": "500",
                "minimum_order_amount": "2000",
                "valid_from": now.strftime("%Y-%m-%dT%H:%M"),
                "valid_to": (now + timezone.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M"),
                "usage_limit": "100",
                "per_user_limit": "1",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        coupon = Coupon.objects.get(code="NEWYEAR")
        self.assertEqual(coupon.value, Decimal("500.00"))

    def test_review_toggle_updates_visibility_and_rating(self):
        review = Review.objects.create(
            product=self.product,
            user=self.customer,
            rating=5,
            title="Five",
            body="An excellent purchase overall.",
        )
        response = self.client.post(reverse("dashboard:review_toggle", args=[review.pk]))
        self.assertEqual(response.status_code, 302)
        review.refresh_from_db()
        self.product.refresh_from_db()
        self.assertFalse(review.is_approved)
        self.assertEqual(self.product.review_count, 0)

    def test_contact_message_status_update(self):
        message = ContactMessage.objects.create(
            name="Help", email="help@example.com", subject="Problem", message="Please help me."
        )
        response = self.client.post(
            reverse("dashboard:contact_message_status", args=[message.pk]),
            {"status": ContactMessage.Status.RESOLVED},
        )
        self.assertEqual(response.status_code, 302)
        message.refresh_from_db()
        self.assertEqual(message.status, ContactMessage.Status.RESOLVED)

    def test_category_can_be_created(self):
        response = self.client.post(
            reverse("dashboard:category_create"),
            {
                "name": "Drones",
                "description": "Camera drones and accessories.",
                "icon": "box",
                "sort_order": "4",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Category.objects.filter(name="Drones").exists())

    def test_brand_can_be_created(self):
        response = self.client.post(
            reverse("dashboard:brand_create"),
            {
                "name": "Nepal Tech",
                "description": "A local brand.",
                "website": "https://example.com",
                "is_active": "on",
                "is_featured": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Brand.objects.filter(name="Nepal Tech").exists())

    def test_customer_suspension_toggle(self):
        response = self.client.post(
            reverse("dashboard:customer_toggle_suspension", args=[self.customer.pk]),
            {"reason": "Fraud review"},
        )
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_suspended)
        self.assertEqual(self.customer.suspension_reason, "Fraud review")

    def test_shipping_method_can_be_added_from_settings(self):
        response = self.client.post(
            reverse("dashboard:store_settings"),
            {
                "form_type": "shipping",
                "shipping-name": "Same Day",
                "shipping-code": "same-day",
                "shipping-description": "Same-day delivery inside the valley.",
                "shipping-charge": "700",
                "shipping-min_days": "1",
                "shipping-max_days": "1",
                "shipping-sort_order": "9",
                "shipping-is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            type(self.order.shipping_method).objects.filter(code="same-day").exists()
        )

    def test_product_delete_removes_product(self):
        response = self.client.post(reverse("dashboard:product_delete", args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
