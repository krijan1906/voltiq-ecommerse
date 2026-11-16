from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.core.models import ContactMessage, NewsletterSubscription, SiteSetting
from apps.core.testing import make_product, make_user
from apps.products.models import Product
from apps.reviews.models import Review


class StorefrontPageTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_home_page_renders_without_products(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Voltiq")

    def test_home_page_shows_active_products(self):
        product = make_product(name="Homepage Hero Product", is_featured=True)
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Homepage Hero Product")
        self.assertIn(product, response.context["hero_products"])

    def test_home_page_hides_inactive_products(self):
        make_product(name="Retired Product", is_active=False)
        response = self.client.get(reverse("core:home"))
        self.assertNotContains(response, "Retired Product")

    def test_health_endpoint(self):
        response = self.client.get(reverse("core:health"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(response["Content-Type"], {"application/json", "application/json; charset=utf-8"})

    def test_robots_txt(self):
        response = self.client.get(reverse("core:robots"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Sitemap", response.content)

    def test_static_content_pages_render(self):
        for name in ("about", "faq", "privacy", "terms", "shipping", "returns"):
            with self.subTest(page=name):
                response = self.client.get(reverse(f"core:{name}"))
                self.assertEqual(response.status_code, 200)

    def test_unknown_url_returns_custom_404(self):
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)


class NewsletterTests(TestCase):
    def test_subscribe_creates_subscription_and_sends_welcome(self):
        response = self.client.post(
            reverse("core:newsletter_subscribe"),
            {"email": "insider@example.com", "name": "Insider"},
        )
        self.assertEqual(response.status_code, 302)
        subscription = NewsletterSubscription.objects.get(email="insider@example.com")
        self.assertTrue(subscription.is_active)
        self.assertTrue(subscription.token)
        self.assertEqual(len(mail.outbox), 1)

    def test_ajax_subscribe_returns_json(self):
        response = self.client.post(
            reverse("core:newsletter_subscribe"),
            {"email": "ajax@example.com"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_ajax_invalid_email_returns_400(self):
        response = self.client.post(
            reverse("core:newsletter_subscribe"),
            {"email": "not-an-email"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_resubscribe_reactivates_existing(self):
        subscription = NewsletterSubscription.objects.create(
            email="returning@example.com", is_active=False, token="token-123"
        )
        self.client.post(reverse("core:newsletter_subscribe"), {"email": "returning@example.com"})
        subscription.refresh_from_db()
        self.assertTrue(subscription.is_active)
        self.assertEqual(NewsletterSubscription.objects.count(), 1)

    def test_unsubscribe_with_token(self):
        subscription = NewsletterSubscription.objects.create(
            email="leaving@example.com", token="unsubscribe-token"
        )
        response = self.client.get(reverse("core:newsletter_unsubscribe", args=[subscription.token]))
        self.assertRedirects(response, reverse("core:home"))
        subscription.refresh_from_db()
        self.assertFalse(subscription.is_active)
        self.assertIsNotNone(subscription.unsubscribed_at)

    def test_invalid_unsubscribe_token_is_handled(self):
        response = self.client.get(reverse("core:newsletter_unsubscribe", args=["missing"]))
        self.assertRedirects(response, reverse("core:home"))


class ContactFormTests(TestCase):
    def test_contact_form_saves_message_and_emails_support(self):
        response = self.client.post(
            reverse("core:contact"),
            {
                "name": "Sujan",
                "email": "sujan@example.com",
                "phone": "+977 980-111-2222",
                "subject": "Warranty question",
                "message": "Does the laptop warranty cover accidental damage?",
            },
        )
        self.assertRedirects(response, reverse("core:contact"))
        message = ContactMessage.objects.get(email="sujan@example.com")
        self.assertEqual(message.status, ContactMessage.Status.NEW)
        self.assertTrue(len(mail.outbox) >= 1)

    def test_short_contact_message_is_rejected(self):
        response = self.client.post(
            reverse("core:contact"),
            {
                "name": "Sujan",
                "email": "sujan@example.com",
                "subject": "Hi",
                "message": "Too short",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ContactMessage.objects.exists())


class SiteSettingTests(TestCase):
    def test_load_is_a_singleton(self):
        first = SiteSetting.load()
        second = SiteSetting.load()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(SiteSetting.objects.count(), 1)

    def test_default_store_identity(self):
        site = SiteSetting.load()
        self.assertEqual(site.store_name, "Voltiq")
        self.assertTrue(site.support_email)
