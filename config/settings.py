"""
Django settings for Voltiq electronics store.

Environment-driven configuration.  PostgreSQL is the production database;
SQLite is available as a local development fallback when PostgreSQL is not
installed (set DB_ENGINE=sqlite in .env).
"""
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(key: str, default: bool = False) -> bool:
    try:
        return config(key, cast=bool, default=default)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = config(
    "SECRET_KEY",
    default="django-insecure-dev-only-change-me-8f2k9s7d6f5g4h3j2k1l",
)
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    cast=Csv(),
    default="localhost,127.0.0.1,[::1],testserver",
)

SITE_NAME = config("SITE_NAME", default="Voltiq")
SITE_URL = config("SITE_URL", default="http://127.0.0.1:8000").rstrip("/")
SUPPORT_EMAIL = config("SUPPORT_EMAIL", default="support@voltiq.com.np")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="Voltiq <no-reply@voltiq.com.np>")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "rest_framework",
    "apps.core",
    "apps.accounts",
    "apps.categories",
    "apps.products",
    "apps.cart",
    "apps.wishlist",
    "apps.orders",
    "apps.payments",
    "apps.inventory",
    "apps.reviews",
    "apps.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.accounts.middleware.SuspendedUserMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database
#   DB_ENGINE=postgres  -> PostgreSQL (production / pgAdmin 4)
#   DB_ENGINE=sqlite    -> local fallback
# ---------------------------------------------------------------------------
DB_ENGINE = config("DB_ENGINE", default="sqlite").strip().lower()

if DB_ENGINE in {"postgres", "postgresql"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="voltiq"),
            "USER": config("DB_USER", default="postgres"),
            "PASSWORD": config("DB_PASSWORD", default="postgres"),
            "HOST": config("DB_HOST", default="127.0.0.1"),
            "PORT": config("DB_PORT", default="5432"),
            "CONN_MAX_AGE": config("DB_CONN_MAX_AGE", cast=int, default=60),
            "OPTIONS": {"connect_timeout": 10},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kathmandu"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

if not DEBUG:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "core:home"

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # AJAX reads the token
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    cast=Csv(),
    default="http://127.0.0.1:8000,http://localhost:8000",
)

# ---------------------------------------------------------------------------
# Security (production toggles — all safe for local HTTP development)
# ---------------------------------------------------------------------------
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", False)
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", cast=int, default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
DATA_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
MAX_UPLOAD_SIZE_MB = config("MAX_UPLOAD_SIZE_MB", cast=int, default=5)
CSRF_FAILURE_VIEW = "apps.core.views.csrf_failure"

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_HOST = config("EMAIL_HOST", default="")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = config("EMAIL_PORT", cast=int, default=587)
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
    EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
    EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
else:
    # Development: verification / reset links are printed to the console.
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_TIMEOUT = 10

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "voltiq-cache",
        "TIMEOUT": 300,
    }
}

# ---------------------------------------------------------------------------
# REST framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "120/min", "user": "300/min"},
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 24,
}

# ---------------------------------------------------------------------------
# Store / payments
# ---------------------------------------------------------------------------
FREE_SHIPPING_THRESHOLD = config("FREE_SHIPPING_THRESHOLD", cast=int, default=10000)
DEFAULT_SHIPPING_FEE = config("DEFAULT_SHIPPING_FEE", cast=int, default=250)
PAYMENT_TIMEOUT_MINUTES = config("PAYMENT_TIMEOUT_MINUTES", cast=int, default=30)
PAYMENT_SIMULATION = env_bool("PAYMENT_SIMULATION", DEBUG)

ESEWA_MODE = config("ESEWA_MODE", default="sandbox")
ESEWA_PRODUCT_CODE = config("ESEWA_PRODUCT_CODE", default="EPAYTEST")
ESEWA_SECRET_KEY = config("ESEWA_SECRET_KEY", default="")
ESEWA_INIT_URL = config(
    "ESEWA_INIT_URL",
    default="https://rc-epay.esewa.com.np/api/epay/main/v2/form",
)
ESEWA_STATUS_URL = config(
    "ESEWA_STATUS_URL",
    default="https://rc.esewa.com.np/api/epay/transaction/status/",
)

KHALTI_MODE = config("KHALTI_MODE", default="sandbox")
KHALTI_SECRET_KEY = config("KHALTI_SECRET_KEY", default="")
KHALTI_INIT_URL = config("KHALTI_INIT_URL", default="https://dev.khalti.com/api/v2/epayment/initiate/")
KHALTI_LOOKUP_URL = config("KHALTI_LOOKUP_URL", default="https://dev.khalti.com/api/v2/epayment/lookup/")
KHALTI_WEBSITE_URL = config("KHALTI_WEBSITE_URL", default=SITE_URL)

# Bank transfer instructions (shown to customers paying by bank deposit)
BANK_NAME = config("BANK_NAME", default="Nabil Bank")
BANK_ACCOUNT_NAME = config("BANK_ACCOUNT_NAME", default="Voltiq Electronics Pvt. Ltd.")
BANK_ACCOUNT_NUMBER = config("BANK_ACCOUNT_NUMBER", default="")
BANK_BRANCH = config("BANK_BRANCH", default="Durbar Marg, Kathmandu")
BANK_SWIFT = config("BANK_SWIFT", default="")
BANK_SUPPORT_NOTE = config(
    "BANK_SUPPORT_NOTE",
    default="Email the deposit slip to support@voltiq.com.np quoting your order number.",
)

STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY", default="")
STRIPE_PUBLISHABLE_KEY = config("STRIPE_PUBLISHABLE_KEY", default="")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "voltiq.log",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# Ensure log directory exists without failing read-only deployments.
try:
    (BASE_DIR / "logs").mkdir(exist_ok=True)
    if not DEBUG:
        LOGGING["root"]["handlers"] = ["console", "file"]
        LOGGING["loggers"]["apps"]["handlers"] = ["console", "file"]
except OSError:
    pass

MESSAGE_TAGS = {
    10: "debug",
    20: "info",
    25: "success",
    30: "warning",
    40: "error",
}
