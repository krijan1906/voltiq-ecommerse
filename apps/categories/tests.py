from django.core.cache import cache
from django.test import TestCase

from apps.categories.models import Brand, Category
from apps.core.testing import make_brand, make_category, make_product


class CategoryModelTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_slug_is_generated_and_unique(self):
        first = make_category(name="Smart Watches")
        second = make_category(name="Smart Watches 2")
        self.assertEqual(first.slug, "smart-watches")
        self.assertNotEqual(second.slug, first.slug)

    def test_product_count_ignores_inactive_products(self):
        category = make_category()
        make_product(category=category)
        make_product(category=category, is_active=False)
        self.assertEqual(category.product_count, 1)
        self.assertEqual(category.all_product_count, 1)

    def test_all_product_count_includes_children(self):
        parent = make_category(name="Laptops")
        child = make_category(name="Gaming Laptops", parent=parent)
        make_product(category=child)
        make_product(category=parent)
        self.assertEqual(parent.product_count, 1)
        self.assertEqual(parent.all_product_count, 2)

    def test_category_str_includes_parent(self):
        parent = make_category(name="Audio")
        child = make_category(name="Headphones", parent=parent)
        self.assertIn("Audio", str(child))
        self.assertIn("Headphones", str(child))

    def test_brand_product_count(self):
        brand = make_brand()
        make_product(brand=brand)
        self.assertEqual(brand.product_count, 1)

    def test_saving_category_invalidates_navigation_cache(self):
        cache.set("nav_categories", ["stale"], 300)
        make_category(name="Fresh Category")
        self.assertIsNone(cache.get("nav_categories"))

    def test_brand_save_invalidates_navigation_cache(self):
        cache.set("nav_categories", ["stale"], 300)
        Brand.objects.create(name="Cache Breaker")
        self.assertIsNone(cache.get("nav_categories"))

    def test_get_absolute_url_points_to_filtered_catalogue(self):
        category = make_category(name="Networking")
        self.assertIn("category=networking", category.get_absolute_url())
