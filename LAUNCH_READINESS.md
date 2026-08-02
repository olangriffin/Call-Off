# Call-Off Launch Readiness

## Result

**Ready with minor caveats**

The public application, secure early-access flow, privacy page, indicative pricing,
production configuration, email integration, migration, error pages, and deployment
definition are implemented. No critical or high-severity launch blocker was found in
the completed source review and automated checks.

The remaining caveats are operational: run the migrations against a disposable empty
PostgreSQL database before the first live deployment, and complete a final visual pass
in a real browser because no in-app browser target was available during this review.

## Verification completed

- 25 real HTTP integration tests passed.
- The permanent top fade and gradual bottom blur render only on the landing page;
  public forms, pricing, and privacy pages remain overlay-free.
- All 21 Jinja templates parsed and passed `djlint`.
- All frontend JavaScript files passed `node --check`.
- Python sources passed `compileall`.
- Installed Python dependencies passed `pip check`.
- Public internal links were crawled and resolved successfully.
- Public copy, legacy domain, CTA, forbidden-character, and secret-pattern scans passed.
- Every server-rendered POST form contains a CSRF token.
- Production configuration accepts a complete secure configuration and rejects an
  unsafe one with a clear startup error.
- The complete migration chain generated valid PostgreSQL SQL from an empty base.
- The launch migration downgraded and upgraded offline with all 13 check constraints.
- Core text and button color pairs meet WCAG AA contrast for normal text.
- Responsive breakpoints, visible focus treatment, and reduced-motion handling were
  verified structurally.

## Files created

- `.djlintrc`
- `.env.example`
- `.python-version`
- `LAUNCH_READINESS.md`
- `README.md`
- `render.yaml`
- `requirements-dev.txt`
- `requirements.txt`
- `app/backend/core/config.py`
- `app/backend/core/csrf.py`
- `app/backend/models/early_access.py`
- `app/backend/services/email_notifications.py`
- `app/backend/services/turnstile.py`
- `app/frontend/static/js/confirm-actions.js`
- `app/frontend/templates/marketing/error.html`
- `app/frontend/templates/marketing/privacy.html`
- `migrations/versions/19a6d640be9d_create_early_access_applications.py`
- `migrations/versions/c4e21d8a3f70_harden_early_access_applications.py`
- `tests/__init__.py`
- `tests/test_public_site.py`

## Files changed

- `.gitignore`
- `Holden/design_reporting_tool.html`
- `Holden/workload_planner.html`
- `app/main.py`
- `app/backend/core/auth.py`
- `app/backend/database/session.py`
- `app/backend/frontend_templates.py`
- `app/backend/models/__init__.py`
- `app/backend/routes/auth.py`
- `app/backend/routes/frontend/__init__.py`
- `app/backend/routes/frontend/deliverables.py`
- `app/backend/routes/frontend/marketing.py`
- `app/backend/routes/frontend/programme_activities.py`
- `app/backend/routes/frontend/projects.py`
- `app/backend/routes/frontend/work_packages.py`
- `app/frontend/static/css/app.css`
- `app/frontend/static/css/marketing.css`
- `app/frontend/static/js/early-access.js`
- `app/frontend/static/js/marketing-nav-menu.js`
- `app/frontend/static/js/smooth-inputs.js`
- `app/frontend/templates/auth/login.html`
- `app/frontend/templates/auth/register.html`
- `app/frontend/templates/base.html`
- `app/frontend/templates/deliverable/approval_new.html`
- `app/frontend/templates/deliverable/deliverable_new.html`
- `app/frontend/templates/deliverable/deliverable_revision_new.html`
- `app/frontend/templates/marketing/base.html`
- `app/frontend/templates/marketing/early_access.html`
- `app/frontend/templates/marketing/landing.html`
- `app/frontend/templates/marketing/pricing.html`
- `app/frontend/templates/package/work_package_new.html`
- `app/frontend/templates/programme/programme.html`
- `app/frontend/templates/programme/programme_activity_edit.html`
- `app/frontend/templates/programme/programme_activity_new.html`
- `app/frontend/templates/project/project_new.html`
- `migrations/env.py`

## Run and test commands

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q app migrations tests
.venv/bin/python -m pip check
.venv/bin/djlint app/frontend/templates --lint --statistics
for file in app/frontend/static/js/*.js; do node --check "$file"; done
```

## Required production environment variables

- `ENVIRONMENT=production`
- `DEBUG=false`
- `DATABASE_URL`
- `APP_BASE_URL`
- `TRUSTED_HOSTS`
- `NEON_AUTH_BASE_URL`
- `AUTH_COOKIE_SECURE=true`
- `ALLOW_PUBLIC_REGISTRATION=false`
- `CONTACT_EMAIL`, using the `calloff.ie` domain
- `LEGAL_ENTITY_NAME`
- `PRIVACY_RETENTION_DAYS`
- `IP_HASH_SECRET`, at least 32 random characters
- `EARLY_ACCESS_RATE_LIMIT`
- `EARLY_ACCESS_RATE_WINDOW_MINUTES`
- `TURNSTILE_SITE_KEY`
- `TURNSTILE_SECRET_KEY`

Optional email settings:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS=true`
- `SMTP_FROM_EMAIL`
- `EARLY_ACCESS_NOTIFICATION_EMAIL`

When SMTP is absent, valid applications are still committed to the database. The
application logs only a safe operational message.

## Database migration instructions

Apply migrations as a release step before starting the new process:

```bash
alembic upgrade head
alembic current
alembic heads
```

Verify the launch migration only in a disposable non-production database:

```bash
alembic downgrade 19a6d640be9d
alembic upgrade head
```

The older `7d7edb21bfc9` migration intentionally cannot downgrade because it removed
an orphaned legacy migration table. This does not affect downgrade and upgrade of the
new early-access migration.

## Render deployment

1. Push the repository to the source provider used by Render.
2. Create a Blueprint from `render.yaml`.
3. Set every `sync: false` value in Render before deploying.
4. Set `APP_BASE_URL` to the final HTTPS origin.
5. Include the Render hostname and every custom hostname in `TRUSTED_HOSTS`.
6. Register the final hostnames in Cloudflare Turnstile.
7. Confirm the pre-deploy command `alembic upgrade head` succeeds.
8. Confirm `/health` returns `{"status":"ok"}` before routing public traffic.

The production command is:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*" --no-access-log
```

The wildcard forwarded-IP trust is appropriate only behind Render's controlled proxy.
Do not use this command when Uvicorn is directly exposed to the internet.

Render references:

- <https://render.com/docs/deploy-fastapi>
- <https://render.com/docs/deploys>
- <https://render.com/docs/blueprint-spec>

## Remaining decisions and risks

- Confirm the actual legal entity name before setting `LEGAL_ENTITY_NAME`.
- Confirm the privacy wording and lawful basis with appropriate legal advice.
- Choose the operational retention period and implement the associated deletion
  process around `PRIVACY_RETENTION_DAYS`.
- Confirm the indicative pricing and founding-customer terms before publishing them.
- Decide whether SMTP notifications are required at launch and select the provider.
- Run a final empty-PostgreSQL online migration check and a browser visual check on
  desktop, tablet, and mobile before opening traffic.
