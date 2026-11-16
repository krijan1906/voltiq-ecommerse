# PostgreSQL with pgAdmin 4

Voltiq uses PostgreSQL as its production database. This guide creates the database and a dedicated user in **pgAdmin 4**, connects Django, and covers backup/restore.

## 1. Install PostgreSQL and pgAdmin 4

Install the official PostgreSQL bundle from <https://www.postgresql.org/download/>. It includes:

- PostgreSQL server
- pgAdmin 4
- `psql`, `pg_dump` and `pg_restore` command-line tools

During installation, remember the `postgres` superuser password. The default port is `5432`.

## 2. Open pgAdmin 4

1. Launch **pgAdmin 4**.
2. If prompted, set a pgAdmin master password.
3. In the left sidebar, expand **Servers**.
4. The installer usually creates a server named **PostgreSQL \<version\>**.
5. Enter the `postgres` password when prompted.

If no server exists, right-click **Servers → Register → Server…**.

### Register dialog

**General** tab:

| Field | Value |
| --- | --- |
| Name | `Voltiq Local` |

**Connection** tab:

| Field | Value |
| --- | --- |
| Host name/address | `127.0.0.1` |
| Port | `5432` |
| Maintenance database | `postgres` |
| Username | `postgres` |
| Password | your PostgreSQL superuser password |
| Save password? | Optional |

Click **Save**.

## 3. Create a dedicated database user

1. Expand **Voltiq Local → Databases**.
2. Right-click **Login/Group Roles → Create → Login/Group Role…**.
3. **General** tab: set **Name** to `voltiq_user`.
4. **Definition** tab: set a strong **Password**.
5. **Privileges** tab: enable **Can login?**.
6. Click **Save**.

Or use Query Tool:

```sql
CREATE USER voltiq_user WITH PASSWORD 'choose-a-strong-password';
```

Replace the password with a unique value and store it securely.

## 4. Create the database

1. Right-click **Databases → Create → Database…**.
2. **General** tab:
   - **Database**: `voltiq`
   - **Owner**: `voltiq_user`
3. **Encoding**: `UTF8`
4. Click **Save**.

Or SQL:

```sql
CREATE DATABASE voltiq OWNER voltiq_user ENCODING 'UTF8';
```

Because `voltiq_user` owns the database, it can create tables in the `public` schema. On PostgreSQL 15+, if you use a different setup, grant schema access explicitly:

```sql
\c voltiq
GRANT ALL ON SCHEMA public TO voltiq_user;
ALTER SCHEMA public OWNER TO voltiq_user;
```

Run these while connected to the `voltiq` database.

## 5. Test the connection

In pgAdmin, right-click the `voltiq` database and choose **Query Tool**, then run:

```sql
SELECT current_database(), current_user, version();
```

You should see `voltiq`, `voltiq_user` and the PostgreSQL version.

### Test from the terminal

If `psql` is on `PATH`:

```powershell
psql -h 127.0.0.1 -p 5432 -U voltiq_user -d voltiq
```

On Windows, if `psql` is not recognized, use the full path, for example:

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -h 127.0.0.1 -p 5432 -U voltiq_user -d voltiq
```

Or add `C:\Program Files\PostgreSQL\<version>\bin` to your `PATH`.

## 6. Configure Voltiq

Edit `.env` in the project root:

```dotenv
DB_ENGINE=postgres
DB_NAME=voltiq
DB_USER=voltiq_user
DB_PASSWORD=choose-a-strong-password
DB_HOST=127.0.0.1
DB_PORT=5432
```

Then run:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_store
```

After migration, refresh pgAdmin: **Schemas → public → Tables** should list Voltiq tables such as `accounts_user`, `products_product`, `orders_order` and `payments_payment`.

## 7. Inspect data in pgAdmin

Useful queries in the Query Tool:

```sql
-- Recent orders
SELECT order_number, status, payment_status, payment_method, total, created_at
FROM orders_order
ORDER BY created_at DESC
LIMIT 20;

-- Low-stock products
SELECT sku, name, stock_quantity, low_stock_threshold
FROM products_product
WHERE stock_quantity <= low_stock_threshold
ORDER BY stock_quantity;

-- Successful payments
SELECT p.transaction_ref, p.gateway, p.amount, p.status, o.order_number
FROM payments_payment p
JOIN orders_order o ON o.id = p.order_id
WHERE p.status = 'success'
ORDER BY p.completed_at DESC;
```

Table and column names follow Django defaults (`<app>_<model>`). The custom user table is `accounts_user`.

## 8. Backup

### pgAdmin GUI

1. Right-click the `voltiq` database → **Backup…**.
2. **Filename**: choose a secure location, e.g. `C:\backups\voltiq-2026-11-16.backup`.
3. **Format**: **Custom** or **Tar**.
4. **Encoding**: `UTF8`.
5. Click **Backup**.

### Command line

```powershell
& "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" `
  -h 127.0.0.1 -p 5432 -U voltiq_user -F c `
  -f "C:\backups\voltiq-2026-11-16.backup" voltiq
```

Also back up the `media/` directory. Database backups do **not** include uploaded images.

## 9. Restore

### pgAdmin GUI

1. Create an empty database (or drop/recreate `voltiq`).
2. Right-click the database → **Restore…**.
3. Select the backup file.
4. Choose **Custom** or **Tar** format as appropriate.
5. Click **Restore**.

### Command line

```powershell
& "C:\Program Files\PostgreSQL\16\bin\pg_restore.exe" `
  -h 127.0.0.1 -p 5432 -U voltiq_user `
  -d voltiq --clean --if-exists "C:\backups\voltiq-2026-11-16.backup"
```

After restoring, run:

```powershell
python manage.py migrate
python manage.py check
```

`migrate` applies any migrations added after the backup was taken.

## 10. Remote/production server

For a hosted PostgreSQL server:

1. In pgAdmin, **Register → Server** with the provider host, port, database and credentials.
2. Require SSL if the provider supports it (**SSL** tab → **SSL mode: require**).
3. Restrict the server firewall to your application server IP.
4. Use a dedicated database user and a strong password.
5. Never expose PostgreSQL directly to the public internet.

Typical production `.env`:

```dotenv
DB_ENGINE=postgres
DB_NAME=voltiq
DB_USER=voltiq_app
DB_PASSWORD=...
DB_HOST=db.internal.example.com
DB_PORT=5432
```

## 11. Troubleshooting

| Problem | Fix |
| --- | --- |
| `password authentication failed` | Verify the password and `pg_hba.conf` authentication method. Re-enter the password in pgAdmin. |
| `database "voltiq" does not exist` | Create it with the correct owner, or fix `DB_NAME`. |
| `permission denied for schema public` | Make `voltiq_user` the schema owner or grant `CREATE`/`USAGE` on `public`. |
| `connection refused` | Start the PostgreSQL service and confirm host/port. |
| `psql` not recognized | Add the PostgreSQL `bin` directory to `PATH` or use the full path. |
| Django still uses SQLite | Set `DB_ENGINE=postgres` in `.env` and restart the server/process. |
| Tables missing after migrate | Confirm Django connected to the intended database and user. Check `python manage.py showmigrations`. |
| Old data after restore | Ensure you restored into the correct database and restarted the application. |

## 12. Security checklist

- Use a dedicated database user, not `postgres`, for the application.
- Use a long, unique password stored in `.env` or a secret manager.
- Back up daily and test restores regularly.
- Keep PostgreSQL and pgAdmin updated.
- Restrict network access and require TLS for remote connections.
- Remove demo data and demo accounts before launch.

See [deployment.md](deployment.md) for the production checklist.
