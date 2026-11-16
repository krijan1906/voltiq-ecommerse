# Voltiq — Production Deployment Guide

This guide covers a single-server deployment (Linux + Gunicorn + Nginx) and a Windows Server alternative (Waitress + IIS/Nginx). Adjust paths and service names to your environment.

## 1. Architecture

```
Internet
   │  HTTPS
   ▼
Nginx / reverse proxy
   ├── /static/  → STATIC_ROOT (built by collectstatic)
   ├── /media/   → MEDIA_ROOT (uploaded images)
   └── /         → Gunicorn/Waitress → Django (WSGI)
                                   ├── PostgreSQL
                                   ├── SMTP provider
                                   └── eSewa / Khalti APIs
```

No WebSocket/Channels service is required.

## 2. Production checklist

Before launch:

- [ ] `DEBUG=False`
- [ ] Unique, strong `SECRET_KEY` (50+ random characters)
- [ ] Real `ALLOWED_HOSTS`
- [ ] `SITE_URL` and `CSRF_TRUSTED_ORIGINS` use the HTTPS domain
- [ ] PostgreSQL database created, migrated and seeded with real data
- [ ] Demo accounts and demo orders removed or secured
- [ ] `PAYMENT_SIMULATION=False`
- [ ] eSewa/Khalti production or approved sandbox credentials configured
- [ ] Bank account details configured
- [ ] SMTP configured and test emails delivered
- [ ] `python manage.py collectstatic --noinput` succeeds
- [ ] `python manage.py check --deploy` reviewed
- [ ] HTTPS certificate installed and HTTP redirects to HTTPS
- [ ] Secure cookies and HSTS enabled
- [ ] Static and media files served by the reverse proxy
- [ ] Database and media backups scheduled and restore-tested
- [ ] Logs monitored and log rotation configured
- [ ] Firewall restricts PostgreSQL and the app port

## 3. Server prerequisites

- Ubuntu 22.04/24.04 LTS (or equivalent)
- Python 3.11+ and `python3-venv`
- PostgreSQL 14+
- Nginx
- Git (optional)
- A domain name and TLS certificate

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip postgresql nginx git
```

## 4. Create the application user and directory

```bash
sudo useradd --system --create-home --shell /bin/bash voltiq
sudo mkdir -p /srv/voltiq
sudo chown voltiq:voltiq /srv/voltiq
```

Deploy the code to `/srv/voltiq` (git clone, rsync or CI artifact), then:

```bash
sudo -u voltiq -H bash
cd /srv/voltiq
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install "gunicorn>=23"
```

On Windows, use Waitress instead of Gunicorn:

```powershell
pip install waitress
```

## 5. Production `.env`

Create `/srv/voltiq/.env` (never commit it):

```dotenv
DEBUG=False
SECRET_KEY=replace-with-a-long-random-secret
ALLOWED_HOSTS=voltiq.com.np,www.voltiq.com.np
SITE_NAME=Voltiq
SITE_URL=https://voltiq.com.np
SUPPORT_EMAIL=support@voltiq.com.np
DEFAULT_FROM_EMAIL=Voltiq <no-reply@voltiq.com.np>
CSRF_TRUSTED_ORIGINS=https://voltiq.com.np,https://www.voltiq.com.np

DB_ENGINE=postgres
DB_NAME=voltiq
DB_USER=voltiq_app
DB_PASSWORD=replace-with-a-strong-password
DB_HOST=127.0.0.1
DB_PORT=5432
DB_CONN_MAX_AGE=60

EMAIL_HOST=smtp.yourprovider.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-smtp-user
EMAIL_HOST_PASSWORD=your-smtp-password

PAYMENT_SIMULATION=False
PAYMENT_TIMEOUT_MINUTES=30

ESEWA_MODE=production
ESEWA_PRODUCT_CODE=your-esewa-product-code
ESEWA_SECRET_KEY=your-esewa-secret
ESEWA_INIT_URL=https://epay.esewa.com.np/api/epay/main/v2/form
ESEWA_STATUS_URL=https://esewa.com.np/api/epay/transaction/status/

KHALTI_MODE=production
KHALTI_SECRET_KEY=your-khalti-secret
KHALTI_INIT_URL=https://khalti.com/api/v2/epayment/initiate/
KHALTI_LOOKUP_URL=https://khalti.com/api/v2/epayment/lookup/
KHALTI_WEBSITE_URL=https://voltiq.com.np

BANK_NAME=Your Bank
BANK_ACCOUNT_NAME=Your Company Pvt. Ltd.
BANK_ACCOUNT_NUMBER=your-account-number
BANK_BRANCH=Your Branch
BANK_SWIFT=YOURSWIFT
BANK_SUPPORT_NOTE=Email the deposit slip to support@voltiq.com.np quoting your order number.

FREE_SHIPPING_THRESHOLD=10000
DEFAULT_SHIPPING_FEE=250

SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=False
```

Generate a secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### Important payment note

Only set `PAYMENT_SIMULATION=False` after the real gateway credentials are in place. If credentials are missing, online gateways are hidden/disabled rather than pretending to charge. Test the full callback flow with gateway sandbox accounts first.

## 6. Database setup

Create the database and user in pgAdmin or SQL:

```sql
CREATE USER voltiq_app WITH PASSWORD 'replace-with-a-strong-password';
CREATE DATABASE voltiq OWNER voltiq_app ENCODING 'UTF8';
```

Then:

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py check
```

Create an administrator if you are not seeding demo data:

```bash
python manage.py createsuperuser
```

> The project uses an **email-based** custom user. `createsuperuser` prompts for an email address and password.

If you need demo data for staging only:

```bash
python manage.py seed_store
```

Remove/disable all demo accounts before production.

## 7. Static files

```bash
python manage.py collectstatic --noinput
```

With `DEBUG=False`, Django uses `CompressedManifestStaticFilesStorage`. Every referenced static file must exist at build time. Re-run `collectstatic` after changing CSS/JS/images and before restarting the app.

The output directory is `/srv/voltiq/staticfiles/`.

## 8. Application server

### Linux: Gunicorn + systemd

Create `/etc/systemd/system/voltiq.service`:

```ini
[Unit]
Description=Voltiq Django application
After=network.target postgresql.service

[Service]
User=voltiq
Group=voltiq
WorkingDirectory=/srv/voltiq
EnvironmentFile=/srv/voltiq/.env
ExecStart=/srv/voltiq/.venv/bin/gunicorn config.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers 3 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now voltiq
sudo systemctl status voltiq
```

Worker sizing: `(2 × CPU cores) + 1` is a reasonable starting point. Increase `--timeout` if PDF invoice generation or large uploads are slow.

### Windows: Waitress

```powershell
waitress-serve --listen=127.0.0.1:8000 config.wsgi:application
```

Run it under a Windows service manager such as NSSM. Put IIS or Nginx in front for TLS and static/media files.

## 9. Nginx reverse proxy

`/etc/nginx/sites-available/voltiq`:

```nginx
upstream voltiq_app {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name voltiq.com.np www.voltiq.com.np;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name voltiq.com.np www.voltiq.com.np;

    ssl_certificate     /etc/letsencrypt/live/voltiq.com.np/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/voltiq.com.np/privkey.pem;

    client_max_body_size 15M;

    access_log /var/log/nginx/voltiq.access.log;
    error_log  /var/log/nginx/voltiq.error.log;

    location /static/ {
        alias /srv/voltiq/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    location /media/ {
        alias /srv/voltiq/media/;
        expires 30d;
        add_header Cache-Control "public";
        access_log off;
    }

    location / {
        proxy_pass http://voltiq_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_read_timeout 60s;
    }
}
```

Enable and reload:

```bash
sudo ln -s /etc/nginx/sites-available/voltiq /etc/nginx/sites-enabled/voltiq
sudo nginx -t
sudo systemctl reload nginx
```

Django already trusts `X-Forwarded-Proto` via `SECURE_PROXY_SSL_HEADER`, so `request.build_absolute_uri()` generates HTTPS callback URLs when Nginx sets the header.

## 10. HTTPS

Use Certbot:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d voltiq.com.np -d www.voltiq.com.np
```

Then enable:

```dotenv
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
```

Only enable `SECURE_HSTS_PRELOAD=True` after you are certain the domain will remain HTTPS-only for the long term.

## 11. Payment gateway configuration

### eSewa

- Configure the merchant/product code and secret in `.env`.
- Set the production initiation and status URLs.
- The callback URL is built from the current request, e.g. `https://voltiq.com.np/payments/esewa/callback/?order=...`.
- Ensure `ALLOWED_HOSTS`, `SITE_URL` and `CSRF_TRUSTED_ORIGINS` match the public domain.
- eSewa responses are verified server-side (HMAC-SHA256) and checked against the status API before the order is marked paid.

### Khalti

- Configure the production merchant secret.
- Set the public website URL to the HTTPS domain.
- The return URL is built from the request, e.g. `https://voltiq.com.np/payments/khalti/callback/?order=...`.
- Khalti callbacks are verified with a server-side lookup; the amount and status are checked before marking the order paid.

### Testing

1. Use sandbox credentials first with `PAYMENT_SIMULATION=False`.
2. Place a real test order through each gateway.
3. Verify the callback marks only the correct order paid.
4. Confirm duplicate callbacks do not create a second successful payment.
5. Confirm failed/cancelled payments leave the order payable.

## 12. Email

Verification and password-reset emails require SMTP. Test:

```bash
python manage.py shell -c "from django.core.mail import send_mail; send_mail('Voltiq test', 'SMTP works', None, ['you@example.com'])"
```

If delivery fails, check provider credentials, TLS/SSL mode, sender verification and spam filters. `EMAIL_TIMEOUT` is 10 seconds.

## 13. Caching across workers

The default cache is `LocMemCache`, which is per process. With multiple Gunicorn workers, cached navigation/site settings may temporarily differ between workers after an update. For multi-worker production, use a shared cache such as Redis:

```bash
pip install "redis>=5"
```

```dotenv
REDIS_URL=redis://127.0.0.1:6379/1
```

and update `CACHES` in `config/settings.py` accordingly. This is optional for a single-worker deployment.

## 14. Logging and monitoring

- Application logs: `logs/voltiq.log` and the systemd journal (`journalctl -u voltiq`).
- Nginx logs: `/var/log/nginx/voltiq.*.log`.
- Configure log rotation (`logrotate`) for `logs/voltiq.log`.
- Monitor `/health/` (returns JSON and a non-200 status if the database/cache check fails).
- Alert on 5xx rates, payment callback failures, disk space and database connections.

## 15. Backups

Back up:

1. PostgreSQL database (`pg_dump` custom format, daily).
2. `media/` directory (product images, avatars).
3. `.env` and configuration (stored securely, not in the web root).
4. TLS certificates (or keep them reproducible via Certbot).

Example backup script:

```bash
#!/usr/bin/env bash
set -euo pipefail
STAMP=$(date +%F-%H%M)
DEST=/var/backups/voltiq
mkdir -p "$DEST"
pg_dump -Fc -U voltiq_app -h 127.0.0.1 voltiq > "$DEST/voltiq-$STAMP.dump"
tar -czf "$DEST/media-$STAMP.tar.gz" -C /srv/voltiq media
find "$DEST" -type f -mtime +30 -delete
```

Test restores regularly. A backup that has never been restored is unverified.

## 16. Deployment sequence

For each release:

```bash
cd /srv/voltiq
source .venv/bin/activate
git pull                      # or deploy the new artifact
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
sudo systemctl restart voltiq
```

Before restarting, confirm migrations are backward-compatible or schedule a maintenance window. For larger teams, use a staging environment and review migrations before production.

## 17. Post-launch smoke test

1. Home page loads over HTTPS with no mixed-content warnings.
2. Product images load from `/media/`.
3. Guest add-to-cart and guest cart persistence work.
4. Registration delivers a verification email.
5. Verified customer can complete each payment method.
6. eSewa/Khalti callbacks mark the correct order paid exactly once.
7. COD and bank-transfer orders appear in the staff dashboard.
8. Staff can update status and stock; the customer sees the timeline.
9. PDF invoice downloads for the owner.
10. `python manage.py check --deploy` has no unresolved warnings.
11. Backups run and a restore has been tested.

## 18. Troubleshooting

| Symptom | Check |
| --- | --- |
| 502 Bad Gateway | Gunicorn/Waitress is not running or the upstream port is wrong. |
| Static files 404 | `collectstatic` was not run, or the Nginx `alias` path is wrong. |
| Media uploads 404 | `MEDIA_ROOT` permissions and the Nginx `/media/` alias. |
| CSRF verification failed | `CSRF_TRUSTED_ORIGINS` must include the exact HTTPS origin. |
| Redirect loops | `SECURE_SSL_REDIRECT` plus a proxy that does not send `X-Forwarded-Proto`. |
| Payment stays pending | Gateway secret/URLs are wrong, or the callback domain is unreachable. |
| Verification email not sent | SMTP is misconfigured; check logs. |
| `DisallowedHost` | Add the domain to `ALLOWED_HOSTS`. |
| `check --deploy` warnings | Address each warning; dev defaults are intentionally insecure. |

## 19. Security notes

- Keep `.env`, database dumps and logs outside the web root.
- Never enable `PAYMENT_SIMULATION` in production.
- Do not store card data; the application never collects card numbers.
- Restrict `/django-admin/` by IP, VPN or strong admin accounts.
- Enforce strong staff passwords and review staff roles regularly.
- Rotate gateway secrets and SMTP passwords periodically.
- Apply Django, Python and OS security updates promptly.
- Use a Web Application Firewall or rate limiting at the edge for additional protection.

For database-specific steps, see [pgadmin.md](pgadmin.md). For local setup, see [setup.md](setup.md).
