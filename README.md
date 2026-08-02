# Call-Off

Call-Off is a FastAPI, Jinja and SQLAlchemy application for specialist
subcontractor delivery coordination. The public website provides product,
indicative pricing, privacy and controlled early-access pages. The authenticated
application retains its existing project, package, deliverable, approval and
programme routes.

## Local setup

1. Create and activate a Python 3.14 virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   For development and template linting, install `requirements-dev.txt`
   instead.

3. Create `.env` from `.env.example` and replace local database and authentication
   values.
4. Apply migrations:

   ```bash
   alembic upgrade head
   ```

5. Start the application:

   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

The public site is available at `http://127.0.0.1:8000` and the readiness check is
available at `/health`.

## Production configuration

The application validates production settings during import and exits with a clear
configuration error when a required control is missing or unsafe.

Required in production:

- `ENVIRONMENT=production`
- `DEBUG=false`
- `DATABASE_URL`: PostgreSQL URL using the `psycopg` driver
- `APP_BASE_URL`: public HTTPS origin, for example `https://calloff.ie`
- `TRUSTED_HOSTS`: comma-separated public hostnames, without `*`
- `NEON_AUTH_BASE_URL`: existing Neon Auth service URL
- `AUTH_COOKIE_SECURE=true`
- `CONTACT_EMAIL`: a configured `calloff.ie` contact address
- `LEGAL_ENTITY_NAME`: the actual operator of Call-Off
- `PRIVACY_RETENTION_DAYS`: between 30 and 3650
- `IP_HASH_SECRET`: at least 32 random characters
- `TURNSTILE_SITE_KEY`
- `TURNSTILE_SECRET_KEY`

Optional email notifications:

- `SMTP_HOST`
- `SMTP_PORT`, default `587`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS`, default `true`
- `SMTP_FROM_EMAIL`
- `EARLY_ACCESS_NOTIFICATION_EMAIL`

If `SMTP_HOST` is omitted, applications are still stored and only a safe operational
message is logged. If SMTP is enabled, both email-address settings are required.

## Database migrations

Apply all migrations before starting a new release:

```bash
alembic upgrade head
```

Check the active revision:

```bash
alembic current
alembic heads
```

To verify the latest early-access migration in a non-production database:

```bash
alembic downgrade 19a6d640be9d
alembic upgrade head
```

Never run downgrade verification against production data. Production startup does
not call `Base.metadata.create_all()`.

## Render deployment

`render.yaml` defines a paid Python web service because Render pre-deploy commands
are used for database migrations.

1. Create a Render Blueprint from this repository.
2. Configure every `sync: false` environment value in the Render dashboard.
3. Set `APP_BASE_URL` to the final HTTPS URL and include the Render hostname and
   custom domains in `TRUSTED_HOSTS`.
4. Configure Cloudflare Turnstile for the final public hostname.
5. Confirm the pre-deploy command completes: `alembic upgrade head`.
6. Confirm `/health` returns `{"status":"ok"}` before routing public traffic.

The production process is:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*" --no-access-log
```

The wildcard proxy allowance is suitable only when the service is reached through
Render's trusted proxy. Do not use it when exposing Uvicorn directly to the public
internet. Access logging is disabled so the application process does not retain raw
client IP addresses.

## Verification

Run the automated public-site suite:

```bash
python -m unittest discover -s tests -v
```

Run source and template checks:

```bash
python -m compileall -q app migrations tests
djlint app/frontend/templates --lint
node --check app/frontend/static/js/early-access.js
node --check app/frontend/static/js/marketing-nav-menu.js
node --check app/frontend/static/js/smooth-inputs.js
```
