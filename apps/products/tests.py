from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.core.testing import make_brand, make_category, make_product, make_user
from apps.products.models import Product, ProductSpecification


class ProductModelTests(TestCase):
    def test_sku_is_uppercased_and_slug_generated(self):
        product = make_product(sku="laptop-001", name="Voltiq Studio Laptop")
        product.refresh_from_db()
        self.assertEqual(product.sku, "LAPTOP-001")
        self.assertEqual(product.slug, "voltiq-studio-laptop")

    def test_slug_uniqueness(self):
        make_product(name="Same Name", sku="SKU-A")
        second = make_product(name="Same Name", sku="SKU-B")
        self.assertNotEqual(second.slug, "same-name")

    def test_current_price_and_discount(self):
        product = make_product(price=Decimal("2500.00"), discount_price=Decimal("1999.00"))
        self.assertEqual(product.current_price, Decimal("1999.00"))
        self.assertTrue(product.has_discount)
        self.assertEqual(product.discount_percent, 20)

    def test_discount_at_or_above_price_is_ignored(self):
        product = make_product(price=Decimal("1000.00"), discount_price=Decimal("1000.00"))
        self.assertIsNone(product.discount_price)
        self.assertEqual(product.current_price, Decimal("1000.00"))

    def test_stock_state_properties(self):
        product = make_product(stock=3, low_stock_threshold=5)
        self.assertTrue(product.in_stock)
        self.assertTrue(product.is_low_stock)
        self.assertIn("Only 3 left", product.stock_label)
        product.stock_quantity = 0
        self.assertFalse(product.in_stock)
        self.assertFalse(product.allow_backorder)
        product.allow_backorder = True
        self.assertTrue(product.in_stock)

    def test_search_matches_name_brand_and_specification(self):
        brand = make_brand(name="Aurora")
        product = make_product(name="Aurora Pro 14", sku="AUR-PRO", brand=brand)
        ProductSpecification.objects.create(product=product, name="GPU", value="RTX 4090")
        self.assertIn(product, Product.objects.search("Aurora"))
        self.assertIn(product, Product.objects.search("RTX 4090"))
        self.assertNotIn(product, Product.objects.search("nothing-like-this"))

    def test_primary_image_property_without_images(self):
        product = make_product()
        self.assertIsNone(product.primary_image)
        self.assertEqual(product.primary_image_url, "")


class ProductViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.laptops = make_category(name="Laptops")
        cls.ultrabooks = make_category(name="Ultrabooks", parent=cls.laptops)
        cls.phones = make_category(name="Phones")
        cls.apple = make_brand(name="Apple-ish")
        cls.samsung = make_brand(name="Samsung-ish")
        cls.ultrabook = make_product(
            name="Feather Ultra 13",
            sku="FEATHER-13",
            category=cls.ultrabooks,
            brand=cls.apple,
            price=Decimal("120000.00"),
            stock=5,
            processor="Intel Core Ultra 7",
        )
        cls.phone = make_product(
            name="Galaxy Test",
            sku="GALAXY-T",
            category=cls.phones,
            brand=cls.samsung,
            price=Decimal("80000.00"),
            stock=0,
        )

    def test_product_list_renders_active_products(self):
        response = self.client.get(reverse("products:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Feather Ultra 13")
        self.assertContains(response, "Galaxy Test")

    def test_search_filters_results(self):
        response = self.client.get(reverse("products:list"), {"q": "Feather"})
        self.assertContains(response, "Feather Ultra 13")
        self.assertNotContains(response, "Galaxy Test")

    def test_parent_category_includes_child_products(self):
        response = self.client.get(reverse("products:list"), {"category": self.laptops.slug})
        self.assertContains(response, "Feather Ultra 13")
        self.assertNotContains(response, "Galaxy Test")

    def test_brand_and_price_filters(self):
        response = self.client.get(
            reverse("products:list"),
            {"brand": self.samsung.slug, "min_price": "50000", "max_price": "90000"},
        )
        self.assertContains(response, "Galaxy Test")
        self.assertNotContains(response, "Feather Ultra 13")

    def test_availability_filter_hides_out_of_stock(self):
        response = self.client.get(reverse("products:list"), {"availability": "in_stock"})
        self.assertContains(response, "Feather Ultra 13")
        self.assertNotContains(response, "Galaxy Test")

    def test_inactive_product_is_hidden_and_detail_404s(self):
        hidden = make_product(name="Hidden Product", sku="HIDDEN-1", is_active=False)
        response = self.client.get(reverse("products:list"))
        self.assertNotContains(response, "Hidden Product")
        detail = self.client.get(reverse("products:detail", kwargs={"slug": hidden.slug}))
        self.assertEqual(detail.status_code, 404)

    def test_product_detail_renders(self):
        response = self.client.get(reverse("products:detail", kwargs={"slug": self.ultrabook.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Feather Ultra 13")
        self.assertContains(response, self.ultrabook.sku)
