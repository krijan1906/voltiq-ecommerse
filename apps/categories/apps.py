from django.apps import AppConfig


class CategoriesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.categories"
    verbose_name = "Categories & Brands"

    def ready(self):
        from apps.categories import signals  # noqa: F401
