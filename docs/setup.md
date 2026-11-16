# Voltiq — Local Setup Guide

This guide takes a clean machine to a running Voltiq storefront, staff dashboard and seeded demo catalogue.

## 1. Prerequisites

| Requirement | Notes |
| --- | --- |
| Python 3.11+ | Python 3.12 or 3.13 recommended; tested on 3.14 |
| pip | Bundled with Python |
| PostgreSQL 14+ | Recommended; SQLite works for a quick start |
| pgAdmin 4 | Optional GUI for PostgreSQL |
| Git | Optional but recommended |
| Internet access | Only needed to download product images during seeding |

Check your versions:

```powershell
python --version
pip --version
```

## 2. Create the project environment

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 3. Create `.env`

```powershell
copy .env.example .env
```

Choose one database mode.

### Option A — SQLite (fastest)

```dotenv
DB_ENGINE=sqlite
DEBUG=True
PAYMENT_SIMULATION=True
```

No database server is required. The file `db.sqlite3` is created on migration.

### Option B — PostgreSQL (recommended)

Create the database first using [pgAdmin 4](pgadmin.md) or SQL:

```sql
CREATE USER voltiq_user WITH PASSWORD 'choose-a-strong-password';
CREATE DATABASE voltiq OWNER voltiq_user;
```

Then set:

```dotenv
DB_ENGINE=postgres
DB_NAME=voltiq
DB_USER=voltiq_user
DB_PASSWORD=choose-a-strong-password
DB_HOST=127.0.0.1
DB_PORT=5432
```

Make sure the PostgreSQL service is running.

### Minimum local values

```dotenv
DEBUG=True
SECRET_KEY=local-development-key-change-me
ALLOWED_HOSTS=localhost,127.0.0.1,[::1],testserver
SITE_URL=http://127.0.0.1:8000
PAYMENT_SIMULATION=True
```

Leave gateway secrets blank for the simulator. Email is printed to the console when `EMAIL_HOST` is empty.

## 4. Migrate

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

## 5. Seed demo data

```powershell
.\.venv\Scripts\python.exe manage.py seed_store
```

The command creates:

- 21 categories and 18 brands
- 26 products with images, specifications and facets
- 14 orders, payments and status histories
- 17 reviews, 3 coupons and shipping methods
- Demo administrator, staff and customer accounts
- Addresses, wishlists, newsletter subscribers, contact messages and notifications
- Site settings and bank-transfer instructions

Options:

```powershell
# Skip Unsplash downloads (fastest; uses generated placeholders)
python manage.py seed_store --skip-images
```

The command is idempotent and safe to re-run. Existing product images are kept.

## 6. Run the development server

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

| URL | Purpose |
| --- | --- |
| http://127.0.0.1:8000/ | Storefront |
| http://127.0.0.1:8000/dashboard/ | Staff dashboard |
| http://127.0.0.1:8000/django-admin/ | Django admin |
| http://127.0.0.1:8000/health/ | Health check |

### Demo accounts

| Role | Email | Password |
| --- | --- | --- |
| Administrator | `admin@voltiq.com` | `Admin@12345` |
| Staff | `staff@voltiq.com` | `Staff@12345` |
| Customer | `aarav.sharma@example.com` | `Customer@12345` |

## 7. Verify the installation

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

Expected: `System check identified no issues` and all tests passing.

Manual checks:

1. Open the home page and a product detail page.
2. Add a product to the cart as a guest.
3. Register a new customer; the verification link is printed in the console.
4. Log in and complete checkout with **Cash on Delivery**.
5. Open `/dashboard/` as the administrator.
6. Download an order PDF invoice from the customer account.

## 8. Email in development

With no SMTP configuration, Django uses the console email backend. Verification and password-reset links appear in the terminal running `runserver`.

To send real email, set:

```dotenv
EMAIL_HOST=smtp.yourprovider.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-user
EMAIL_HOST_PASSWORD=your-password
DEFAULT_FROM_EMAIL=Voltiq <no-reply@yourdomain.com>
```

## 9. Payment simulation

With `DEBUG=True` and `PAYMENT_SIMULATION=True`, online gateways without credentials route to the development simulator. The UI labels sandbox mode, and the simulator page states that no real money moves.

To test real gateway code, add sandbox credentials and set:

```dotenv
PAYMENT_SIMULATION=False
```

Never enable the simulator in production.

## 10. Static and media files

- `static/` contains source CSS, JavaScript and icons used in development.
- `media/` receives uploaded product images and avatars.
- In development, Django serves both automatically when `DEBUG=True`.
- In production run `collectstatic` and serve media through the reverse proxy or object storage.

## 11. Common issues

### `psql` is not recognized

PostgreSQL client tools are not on `PATH`. Either add `C:\Program Files\PostgreSQL\<version>\bin` to `PATH` or use pgAdmin 4. Alternatively set `DB_ENGINE=sqlite`.

### `connection refused` on PostgreSQL

- Confirm the PostgreSQL service is running.
- Check `DB_HOST` and `DB_PORT`.
- Confirm the database and user exist and the password is correct.

### `No directory at: .../staticfiles/`

This warning appears under tests when `collectstatic` has not run. It is harmless in development. Run `python manage.py collectstatic --noinput` for production.

### Images do not load after seeding

- Ensure `media/` exists and is writable.
- In development, `DEBUG=True` must be set so Django serves media.
- Re-run `python manage.py seed_store` without `--skip-images`.

### Verification email not received

In development, look at the `runserver` console. In production, verify SMTP settings and spam filtering.

### Port 8000 already in use

```powershell
python manage.py runserver 8001
```

### Reset the local database

For SQLite:

```powershell
Remove-Item db.sqlite3
python manage.py migrate
python manage.py seed_store
```

For PostgreSQL, drop and recreate the database in pgAdmin, then migrate and seed.

### PowerShell exits with code 1 while tests pass

PowerShell may surface stderr from Django's test database messages as a native-command error. If the output says `OK`, the suite passed. Use `$LASTEXITCODE` or run tests without piping through `Tee-Object` for a clean exit code.

## 12. Next steps

- [pgAdmin 4 guide](pgadmin.md)
- [Production deployment](deployment.md)
- [Project README](../README.md)
