from django.test import TestCase
from django.urls import reverse

from apps.core.testing import make_order, make_product, make_user
from apps.orders.models import Order
from apps.products.models import Product
from apps.reviews.models import Review

VALID_REVIEW = {
    "rating": "5",
    "title": "Excellent purchase",
    "body": "This product has exceeded my expectations in every way during daily use.",
}


class ReviewCreationTests(TestCase):
    def setUp(self):
        self.user = make_user(email="reviewer@example.com")
        self.product = make_product()
        self.client.force_login(self.user)

    def test_purchase_marks_review_as_verified(self):
        make_order(
            user=self.user,
            product=self.product,
            status=Order.Status.DELIVERED,
            payment_status=Order.PaymentStatus.PAID,
        )
        response = self.client.post(
            reverse("reviews:add", args=[self.product.slug]), VALID_REVIEW
        )
        self.assertEqual(response.status_code, 302)
        review = Review.objects.get(product=self.product, user=self.user)
        self.assertTrue(review.is_verified_purchase)
        self.assertTrue(review.is_approved)
        self.assertEqual(review.rating, 5)

    def test_review_without_purchase_is_not_verified(self):
        self.client.post(reverse("reviews:add", args=[self.product.slug]), VALID_REVIEW)
        review = Review.objects.get(product=self.product, user=self.user)
        self.assertFalse(review.is_verified_purchase)

    def test_cancelled_order_does_not_count_as_purchase(self):
        make_order(user=self.user, product=self.product, status=Order.Status.CANCELLED)
        self.client.post(reverse("reviews:add", args=[self.product.slug]), VALID_REVIEW)
        review = Review.objects.get(product=self.product, user=self.user)
        self.assertFalse(review.is_verified_purchase)

    def test_short_review_body_is_rejected(self):
        response = self.client.post(
            reverse("reviews:add", args=[self.product.slug]),
            {**VALID_REVIEW, "body": "Too short"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Review.objects.filter(product=self.product, user=self.user).exists())

    def test_duplicate_review_redirects(self):
        Review.objects.create(
            product=self.product,
            user=self.user,
            rating=4,
            title="First",
            body="A sufficiently long review body for validation.",
        )
        response = self.client.post(
            reverse("reviews:add", args=[self.product.slug]), VALID_REVIEW
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Review.objects.filter(product=self.product, user=self.user).count(), 1)

    def test_review_requires_login(self):
        self.client.logout()
        response = self.client.post(reverse("reviews:add", args=[self.product.slug]), VALID_REVIEW)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])


class ReviewEditingTests(TestCase):
    def setUp(self):
        self.owner = make_user(email="owner@example.com")
        self.other = make_user(email="not-owner@example.com")
        self.product = make_product()
        self.review = Review.objects.create(
            product=self.product,
            user=self.owner,
            rating=4,
            title="Good",
            body="A perfectly reasonable review with enough detail.",
        )

    def test_owner_can_edit_review(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("reviews:edit", args=[self.review.pk]),
            {**VALID_REVIEW, "title": "Updated title"},
        )
        self.assertEqual(response.status_code, 302)
        self.review.refresh_from_db()
        self.assertEqual(self.review.title, "Updated title")
        self.assertEqual(self.review.rating, 5)

    def test_other_user_cannot_edit_review(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("reviews:edit", args=[self.review.pk]))
        self.assertEqual(response.status_code, 404)

    def test_owner_can_delete_review(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("reviews:delete", args=[self.review.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Review.objects.filter(pk=self.review.pk).exists())

    def test_other_user_cannot_delete_review(self):
        self.client.force_login(self.other)
        response = self.client.post(reverse("reviews:delete", args=[self.review.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Review.objects.filter(pk=self.review.pk).exists())


class ReviewRatingSignalTests(TestCase):
    def test_approved_reviews_update_product_aggregate(self):
        product = make_product()
        first_user = make_user(email="rating-1@example.com")
        second_user = make_user(email="rating-2@example.com")

        Review.objects.create(
            product=product, user=first_user, rating=5, title="Five", body="Excellent product overall."
        )
        product.refresh_from_db()
        self.assertEqual(product.rating_avg, 5.0)
        self.assertEqual(product.review_count, 1)

        second = Review.objects.create(
            product=product,
            user=second_user,
            rating=3,
            title="Three",
            body="Average product with some flaws.",
            is_approved=False,
        )
        product.refresh_from_db()
        self.assertEqual(product.review_count, 1)

        second.is_approved = True
        second.save(update_fields=["is_approved"])
        product.refresh_from_db()
        self.assertEqual(product.review_count, 2)
        self.assertEqual(product.rating_avg, 4.0)

    def test_deleting_review_recalculates_rating(self):
        product = make_product()
        user = make_user(email="rating-delete@example.com")
        review = Review.objects.create(
            product=product, user=user, rating=4, title="Four", body="Solid product for the price."
        )
        review.delete()
        product.refresh_from_db()
        self.assertEqual(product.rating_avg, 0)
        self.assertEqual(product.review_count, 0)
