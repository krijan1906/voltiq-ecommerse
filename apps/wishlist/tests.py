from django.test import TestCase
from django.urls import reverse

from apps.cart.models import Cart
from apps.core.testing import make_product, make_user
from apps.wishlist.models import Wishlist, WishlistItem


class WishlistTests(TestCase):
    def setUp(self):
        self.user = make_user(email="wishlist@example.com")
        self.product = make_product(name="Saved Headphones", stock=5)

    def test_toggle_requires_authentication(self):
        response = self.client.post(reverse("wishlist:toggle"), {"product_id": self.product.pk})
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.json()["auth_required"])

    def test_toggle_adds_and_removes_product(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("wishlist:toggle"), {"product_id": self.product.pk})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["added"])
        self.assertEqual(response.json()["wishlist_count"], 1)
        self.assertTrue(
            WishlistItem.objects.filter(wishlist__user=self.user, product=self.product).exists()
        )

        response = self.client.post(reverse("wishlist:toggle"), {"product_id": self.product.pk})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["added"])
        self.assertEqual(response.json()["wishlist_count"], 0)

    def test_toggle_rejects_inactive_products(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])
        self.client.force_login(self.user)
        response = self.client.post(reverse("wishlist:toggle"), {"product_id": self.product.pk})
        self.assertEqual(response.status_code, 404)

    def test_wishlist_page_requires_sign_in(self):
        response = self.client.get(reverse("wishlist:detail"))
        self.assertEqual(response.status_code, 302)

    def test_wishlist_page_lists_saved_products(self):
        wishlist = Wishlist.objects.create(user=self.user)
        WishlistItem.objects.create(wishlist=wishlist, product=self.product)
        self.client.force_login(self.user)
        response = self.client.get(reverse("wishlist:detail"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Saved Headphones")

    def test_remove_item_is_scoped_to_owner(self):
        other = make_user(email="wishlist-other@example.com")
        wishlist = Wishlist.objects.create(user=other)
        item = WishlistItem.objects.create(wishlist=wishlist, product=self.product)
        self.client.force_login(self.user)
        response = self.client.post(reverse("wishlist:remove", args=[item.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(WishlistItem.objects.filter(pk=item.pk).exists())

    def test_move_to_cart_removes_wishlist_item(self):
        wishlist = Wishlist.objects.create(user=self.user)
        item = WishlistItem.objects.create(wishlist=wishlist, product=self.product)
        self.client.force_login(self.user)
        response = self.client.post(reverse("wishlist:move_to_cart", args=[item.pk]))
        self.assertRedirects(response, reverse("cart:detail"))
        self.assertFalse(WishlistItem.objects.filter(pk=item.pk).exists())
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.get(product=self.product).quantity, 1)

    def test_move_to_cart_keeps_item_when_out_of_stock(self):
        self.product.stock_quantity = 0
        self.product.save(update_fields=["stock_quantity"])
        wishlist = Wishlist.objects.create(user=self.user)
        item = WishlistItem.objects.create(wishlist=wishlist, product=self.product)
        self.client.force_login(self.user)
        response = self.client.post(reverse("wishlist:move_to_cart", args=[item.pk]))
        self.assertRedirects(response, reverse("cart:detail"))
        self.assertTrue(WishlistItem.objects.filter(pk=item.pk).exists())
