# Voltiq — Premium Electronics Store

**Voltiq** is a complete, production-oriented electronics e-commerce application built with Django, Django REST Framework and vanilla JavaScript. It is designed for the Nepali market with NPR pricing, eSewa/Khalti wallets, cash on delivery, bank transfer, verified-purchase reviews and a staff analytics dashboard.

> **Tagline:** Premium electronics, powered for life.

---

## Highlights

### Storefront
- Responsive, custom design system (no Bootstrap/Tailwind/React/Vue)
- Editorial hero, category tiles, trending, bestsellers, latest arrivals, deals and recommendations
- Brand showcase, verified customer testimonials, newsletter signup and rich footer
- AJAX product search suggestions, filters (category, brand, price, availability), sorting and pagination
- Dynamic, per-category specification fields with denormalised facets for filtering
- Product quick view, gallery, stock labels, wishlist and related products
- Toast notifications, skeleton loaders, accessible focus states, empty and error states
- Custom 400/403/404/500 pages

### Shopping
- Session-backed guest carts, persistent customer carts and automatic guest-cart merge on login
- Row-locked stock checks on add/update/checkout and clear stock-conflict warnings
- Coupons with percentage/fixed discounts, minimum order value, caps, usage and per-user limits
- Wishlist with move-to-cart and back-in-stock notifications
- Five-step checkout: contact → address → delivery → review → payment
- Shipping methods with fees, free-shipping threshold and delivery estimates
- Order confirmation, tracking timeline, cancellation with restock, reorder and PDF invoices

### Accounts
- Custom email-based user model (roles: customer, staff, administrator)
- Registration with email verification, resend verification, password reset and password change
- Profile, avatar, phone/newsletter preferences, saved addresses and default address
- Order history, payment history and in-app notifications
- Suspended-account enforcement at login and on every request

### Payments
- **eSewa ePay v2** — HMAC-SHA256 signed redirect, callback verification and status lookup
- **Khalti ePayment v2** — server-side initiation and lookup verification
- **Cash on delivery**, **bank transfer** and an optional Stripe gateway stub
- No card numbers, CVVs or gateway secrets are stored; only gateway references and non-sensitive payloads
- One successful payment per order enforced by a database constraint
- Immutable `PaymentTransaction` audit trail and manual refund/COD collection services
- Clearly labelled development simulator when `PAYMENT_SIMULATION=True`; **disabled in production**

### Staff dashboard (`/dashboard/`)
- KPI overview, 30-day revenue chart, payment mix and order-status charts (Chart.js)
- Product CRUD, multi-image upload, primary image, category/brand/specification management
- Order management, status timeline, courier/tracking, cancellation and refunds
- Customer directory, suspension and role management
- Inventory levels, low-stock alerts, stock adjustments and complete stock history
- Review moderation, coupons, newsletter subscribers, contact messages
- CSV exports (orders, newsletter) with spreadsheet-injection protection
- Store settings, shipping methods and bank-transfer instructions
- Role gates: staff for operations, administrator for settings/refunds/roles

### Engineering
- Normalised schema, database constraints, indexes and audit models
- Transactional order placement and stock mutations with `select_for_update`
- Cached navigation/site settings with signal invalidation
- File cleanup signals for replaced/deleted images and avatars
- Rate-limited newsletter endpoint, CSRF-aware AJAX, secure cookies and production security toggles
- 151 automated tests covering models, services, views, permissions, payments, checkout, inventory and dashboard

---

## Tech stack

| Layer | Technology |
| --- | --- |
| Language | Python 3.11+ (tested on Python 3.14) |
| Web framework | Django 5.2 |
| API | Django REST Framework |
| Database | PostgreSQL (production); SQLite (local fallback) |
| Frontend | HTML5, CSS3, vanilla JavaScript |
| Images | Pillow |
| PDF invoices | ReportLab |
| Static files | WhiteNoise |
| Config | python-decouple + `.env` |
| Rate limiting | django-ratelimit |
| Payments | eSewa ePay v2, Khalti ePayment v2, COD, bank transfer |
| Testing | Django test runner |

---

## Quick start (SQLite)

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate         # Linux / macOS

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create local configuration
copy .env.example .env              # Windows
# cp .env.example .env              # Linux / macOS

# 4. Edit .env and set:
#    DB_ENGINE=sqlite
#    DEBUG=True
#    PAYMENT_SIMULATION=True

# 5. Migrate and create demo data
python manage.py migrate
python manage.py seed_store

# 6. Run
python manage.py runserver
```

Open **http://127.0.0.1:8000/**.

### Demo accounts

| Role | Email | Password | Access |
| --- | --- | --- | --- |
| Administrator | `admin@voltiq.com` | `Admin@12345` | Storefront, staff dashboard, settings, Django admin |
| Staff | `staff@voltiq.com` | `Staff@12345` | Storefront and staff dashboard (no settings/refunds) |
| Customer | `aarav.sharma@example.com` | `Customer@12345` | Storefront and customer account |

All seeded accounts are email-verified. Other seeded customers use the same `Customer@12345` password.

- Storefront: `http://127.0.0.1:8000/`
- Staff dashboard: `http://127.0.0.1:8000/dashboard/`
- Django admin: `http://127.0.0.1:8000/django-admin/`

---

## PostgreSQL (recommended)

PostgreSQL is the intended production database. Create the database and user in **pgAdmin 4**, then set:

```dotenv
DB_ENGINE=postgres
DB_NAME=voltiq
DB_USER=voltiq_user
DB_PASSWORD=choose-a-strong-password
DB_HOST=127.0.0.1
DB_PORT=5432
```

Run `python manage.py migrate` and `python manage.py seed_store`.

Detailed walkthrough: [`docs/pgadmin.md`](docs/pgadmin.md)

---

## Environment configuration

Copy `.env.example` to `.env`. Important groups:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Django cryptographic key — generate a unique production value |
| `DEBUG` | Must be `False` in production |
| `ALLOWED_HOSTS` | Comma-separated production hostnames |
| `DB_ENGINE` | `postgres` or `sqlite` |
| `SITE_URL`, `SITE_NAME`, `SUPPORT_EMAIL` | Store identity and absolute links |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP delivery; leave blank to print emails to the console |
| `PAYMENT_SIMULATION` | Development simulator only — set `False` in production |
| `ESEWA_*` | eSewa product code, secret, initiation and status URLs |
| `KHALTI_*` | Khalti secret key, initiation/lookup URLs and website URL |
| `BANK_*` | Bank-transfer instructions shown after checkout |
| `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS` | HTTPS hardening |
| `CSRF_TRUSTED_ORIGINS` | Full HTTPS origins of the production site |

Never commit `.env`. Only `.env.example` belongs in version control.

---

## Payments: sandbox vs production

### Development simulator

With `DEBUG=True` and `PAYMENT_SIMULATION=True`, online gateways without credentials use the built-in simulator. The payment page shows a **Sandbox** badge and the simulator screen explicitly states that no real money moves. This is only for development and testing.

### eSewa ePay v2

1. Register a merchant/test account and obtain the product code and secret key.
2. Set `ESEWA_MODE`, `ESEWA_PRODUCT_CODE`, `ESEWA_SECRET_KEY`, `ESEWA_INIT_URL` and `ESEWA_STATUS_URL`.
3. Use sandbox URLs while testing and production URLs after merchant approval.
4. Set `PAYMENT_SIMULATION=False`.
5. The callback is verified server-side with HMAC-SHA256 and confirmed against the eSewa status API before an order is marked paid.

### Khalti ePayment v2

1. Obtain a merchant secret key from Khalti.
2. Set `KHALTI_SECRET_KEY`, `KHALTI_INIT_URL`, `KHALTI_LOOKUP_URL` and `KHALTI_WEBSITE_URL`.
3. Set `PAYMENT_SIMULATION=False`.
4. Khalti initiation happens server-side; the callback performs a server-side lookup and validates the amount/status before marking the order paid.

### Cash on delivery and bank transfer

COD requires staff to mark cash collected. Bank transfer shows the configured account details and asks the customer to send the deposit slip; staff verify and record the payment manually.

> **Security:** card details are never collected or stored. Gateway secrets stay server-side. Only payment references and non-sensitive response payloads are persisted.

---

## Management commands

```bash
python manage.py migrate                 # apply migrations
python manage.py seed_store              # idempotent demo catalogue + orders
python manage.py seed_store --skip-images # faster, no image downloads
python manage.py createsuperuser         # optional Django admin account
python manage.py collectstatic --noinput  # production static files
python manage.py check --deploy          # production security review
python manage.py test                    # full automated suite
```

The seed command downloads product photography from Unsplash and falls back to generated gradient placeholders when offline. It is safe to re-run.

---

## Project structure

```
ecommerce/
├── apps/
│   ├── accounts/      # User, profile, addresses, verification, notifications
│   ├── cart/          # Guest/customer carts, coupon application, merge signal
│   ├── categories/    # Categories and brands
│   ├── core/          # Home, policies, newsletter, contact, settings, seed command
│   ├── dashboard/     # Staff dashboard views, forms and exports
│   ├── inventory/     # Stock adjustments, audit history, restock notifications
│   ├── orders/        # Orders, checkout, coupons, shipping, PDF invoices
│   ├── payments/      # Payment attempts, gateways, callbacks, simulator
│   ├── products/      # Products, images, specifications, search/filter views
│   ├── reviews/       # Verified-purchase reviews and rating aggregation
│   └── wishlist/      # Wishlist and restock alerts
├── config/            # Settings, root URLs, WSGI/ASGI
├── docs/              # PDF manual, setup, pgAdmin and deployment guides
├── static/            # Modular CSS, vanilla JS, icons and images
├── templates/         # Storefront, checkout, account, dashboard, email and error templates
├── media/             # Uploaded product images and avatars (not committed)
├── manage.py
├── requirements.txt
└── .env.example
```

---

## Tests

```bash
python manage.py test
```

The suite covers:

- Authentication, registration, verification, password flows and access guards
- Product model rules, search, filters, detail rendering and stock states
- Cart stock limits, coupons, guest merge, summaries and AJAX endpoints
- Transactional checkout, stock deduction/history, cancellation/restock and invoices
- Payment state transitions, duplicate-success prevention, simulator and bank instructions
- Inventory adjustments, restock alerts and low-stock behaviour
- Reviews, verified purchases, rating aggregation and ownership rules
- Wishlist toggling, ownership and move-to-cart
- Home/health/newsletter/contact/policy pages and custom error handling
- Dashboard permissions, pages, CRUD actions, order status updates, CSV exports and settings

Current status: **151 tests passing**.

---

## Documentation

- [`docs/Voltiq-Project-Documentation.pdf`](docs/Voltiq-Project-Documentation.pdf) — the complete 93-page project manual (architecture, features, data model, payments, operations, deployment)
- [`docs/setup.md`](docs/setup.md) — local setup, PostgreSQL, assets, email and troubleshooting
- [`docs/pgadmin.md`](docs/pgadmin.md) — creating the Voltiq database/user in pgAdmin 4, backups and restores
- [`docs/deployment.md`](docs/deployment.md) — production checklist, WSGI server, HTTPS, static/media, payments and backups

---

## Production notes

- Set `DEBUG=False`, a unique `SECRET_KEY`, real `ALLOWED_HOSTS` and HTTPS origins.
- Set `PAYMENT_SIMULATION=False` and configure real/sandbox gateway credentials.
- Use PostgreSQL and scheduled backups.
- Serve static files with WhiteNoise/`collectstatic`; serve uploaded media through the reverse proxy or object storage.
- Enable secure cookies, SSL redirect, HSTS and a valid TLS certificate.
- Configure SMTP so verification and password-reset emails are delivered.
- Run `python manage.py check --deploy` and address every warning before launch.

See [`docs/deployment.md`](docs/deployment.md) for the full checklist.

---

## License and attribution

This project was built as a bespoke e-commerce application. Product names and brand marks referenced by demo data belong to their respective owners. Unsplash photography is used under the Unsplash License for demonstration purposes. Replace demo content and imagery before a commercial launch.
