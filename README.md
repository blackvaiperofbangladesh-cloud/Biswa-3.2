# Biswa-3.2 — IN16 Study Manager

Django application for student registration, notes, units, groups, announcements,
and reminders. Source: https://github.com/blackvaiperofbangladesh-cloud/Biswa-3.2.

## Requirements

- Python 3.12 (`.python-version`), pip, and the pinned `requirements.txt`.
- PostgreSQL for Vercel, with a dedicated non-production database for Preview.
- PostgreSQL client tools for owner-operated backups and migration maintenance.
- Vercel access to the intended project, and repository write access for deployment.

## Local installation

```bash
git clone https://github.com/blackvaiperofbangladesh-cloud/Biswa-3.2.git
cd Biswa-3.2
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')"
export DEBUG=True
export ALLOWED_HOSTS=localhost,127.0.0.1
export CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
export DATABASE_URL=sqlite:///db.sqlite3
python manage.py check
python manage.py migrate --plan
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py runserver
```

Open http://127.0.0.1:8000/. SQLite is local development only, not serverless storage.
`.env.example` documents configuration; Django does **not** automatically load `.env`.
Export variables in your shell or use a trusted environment-file loader. Never commit
populated environment files. Optional `python manage.py seed` works only with DEBUG
and SQLite, creates no administrator, and gives demo accounts unusable passwords.
It does not offer a destructive clear option. Create an administrator interactively
with `python manage.py createsuperuser` if needed.

## Environment configuration

| Variable | Required behavior |
| --- | --- |
| `SECRET_KEY` | New independently generated random secret per environment; no source fallback. |
| `DATABASE_URL` | PostgreSQL URL outside development; no production fallback. |
| `DEBUG` | `False` on Vercel (enforced); `True` only for local development. |
| `ALLOWED_HOSTS` | Comma-separated exact hosts, no scheme; never `*`. |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated exact HTTPS origins for your domains. |

Vercel's trusted `VERCEL_URL` adds the exact deployment host and HTTPS origin, not a
wildcard for unrelated deployments. Configure custom domains explicitly.
Use separate production and Preview secrets and database URLs. Production host:
`biswa-3-2-kappa.vercel.app`. Ownership/routing of `biswa-3-2.vercel.app` must be checked
before adding it. HTTPS redirects, secure cookies and HSTS are enabled outside DEBUG;
sessions are HttpOnly with SameSite=Lax. CSRF middleware remains enabled.

### PostgreSQL connections

Obtain a **rotated** URL from the authorized database owner and store it directly in
the target environment's secret store, not in chat, commands committed to Git, or logs.
URL-encode special characters in the username/password. Template only:

```text
postgresql://DB_USER:URL_ENCODED_PASSWORD@DB_HOST:5432/DB_NAME?sslmode=require
```

PostgreSQL SSL is required. Connections are not retained across serverless requests;
server-side cursors are disabled for transaction-pooler compatibility. Use the
provider-approved direct or session connection for migration maintenance. A pooled
runtime URL and a maintenance URL must refer to the **same** intended database/schema.
Do not infer database ownership from old credentials or a hostname alone.

## Safe production migration procedure — owner gate

`notes_app/migrations/0001_initial.py` creates `Student` and the other application
models. A committed migration does not establish that it has run in production.
No migration runs in `build_files.sh`, the WSGI entrypoint, or request handlers.

Before changing production:

1. Confirm the deployment's database identity, schema/search path, database role,
   provider project and authorized owner. Do not use credentials exposed in Git.
2. Take a timestamped provider backup or encrypted `pg_dump --format=custom` backup.
   Use a secure connection mechanism, not a password argument. Verify the backup by
   restoring it into an isolated database; record timestamp, restore result, and
   retention location. A backup listing alone is not a restore verification.
3. Record user/profile counts and migration state privately. Read-only SQL checks:

   ```sql
   SELECT current_database(), current_user, current_schema();
   SHOW search_path;
   SELECT to_regclass('public.notes_app_student');
   SELECT app, name, applied FROM django_migrations ORDER BY app, name;
   ```

   Inspect the actual configured schema if it is not `public`. If `django_migrations`
   is absent, inspect database initialization rather than faking migration history.
4. With the verified maintenance URL securely set as `DATABASE_URL`, execute:

   ```bash
   python manage.py check
   python manage.py showmigrations
   python manage.py migrate --plan
   ```

5. Review every operation. Stop if the plan is destructive, ownership is uncertain,
   migration history disagrees with physical tables, or backup recovery is unverified.
   Only after these gates pass:

   ```bash
   python manage.py migrate --noinput
   python manage.py showmigrations
   python manage.py migrate --check
   ```

6. Verify physical tables and constraints, compare existing record counts, and then
   verify the application. Never use `--fake`, reset the database, or manually create
   tables to conceal a mismatch.

### Previously incomplete accounts

A historical registration could have saved a User without its Student. In the
verified database, inventory candidates read-only with
`User.objects.filter(student__isnull=True, is_staff=False, is_superuser=False)`.
Not every candidate is a failed registration. Review owner-side creation dates and
support evidence, verify account ownership, and collect the correct registration
number/gender through an authorized flow. Back up first; propose individual atomic
profile repairs for owner approval. Do not delete users, infer identity, reset
passwords, or publish the candidate list.

## Registration and authentication

- `/register/` validates Django passwords and normalized registration-number uniqueness.
- `RegisterForm.save()` saves User and Student in one transaction. Profile failure
  rolls back the new User. `commit=False` writes neither record; the caller must
  explicitly handle profile creation if using that API.
- Concurrent uniqueness conflicts display a generic validation error. Database
  availability/schema failures return a generic **503**, not a success claim; the
  missing migration still needs repair.
- `/login/` uses Django authentication and database-backed sessions; successful
  registration logs in the new account and redirects to `/`.
- `/logout/` requires a CSRF-protected POST. GET does not log a user out.
- Dashboard, notes, units, groups, class list, announcements and reminders require login.
- Reminder completion also requires a CSRF-protected POST and ownership check.

## Automated tests

With the local environment configured above:

```bash
python manage.py test notes_app --verbosity 2
python manage.py makemigrations --check --dry-run
python manage.py check
```

Django creates a separate test database and uses synthetic `example.invalid` accounts.
Coverage includes transactional rollback, duplicate and concurrent registration,
password rejection, login/session/logout, protected routes, CSRF, cookie flags,
existing-account preservation and safe seeding. Local SQLite tests do not establish
production PostgreSQL health. Repeat in an isolated PostgreSQL test environment and
run browser acceptance tests against Preview before production approval.

## Vercel deployment

Native Django support detects `manage.py` and resolves
`IN16_Study_Manager.wsgi.application`. `vercel.json` intentionally has no legacy
`builds` or catch-all routes. Vercel installs dependencies, automatically runs
`collectstatic` for `STATIC_ROOT`, and serves static assets through its CDN.
`api/index.py` remains a compatible WSGI wrapper; there are no startup migrations.
`build_files.sh` is an optional local/manual static build, not a migration hook.
WhiteNoise uses the current Django `STORAGES` configuration.

1. Verify the Vercel Git connection is this repository and the production branch is
   `main`; do not substitute another team's project.
2. In the project's **Environment Variables** sidebar page, configure the variables
   above for **Preview**, using an isolated PostgreSQL database and new secrets.
   Store secrets with the Secret type. Set production variables separately only
   after owner-coordinated credential rotation and database backup gates.
3. On the isolated Preview database, review and apply migrations using the safe
   procedure above. Deploy the repair branch/PR to Preview, not Production.
4. Inspect build and Runtime Logs; verify the exact PR head commit. Test register,
   Student row creation, dashboard, login persistence, CSRF, logout, protected routes,
   and `/static/image/bell.svg` with synthetic accounts only.
5. **Do not merge, promote or deploy Production without explicit owner approval.**
   Environment-variable changes apply only to new deployments.

References: [Django on Vercel](https://vercel.com/docs/frameworks/full-stack/django),
[environment variables](https://vercel.com/docs/environment-variables/managing-environment-variables).

## Troubleshooting

| Symptom | Safe next step |
| --- | --- |
| `relation notes_app_student does not exist` | Verify database/schema, backup restoration and migration history; review `migrate --plan`. Do not fake migrations. |
| Registration returns 503 | Check DB availability/schema in private logs and complete the migration gate; retry only after repair. |
| Username unavailable after a failed historical registration | Owner reviews incomplete accounts; never delete the account automatically. |
| Settings fail at startup/build | Set fresh `SECRET_KEY`, PostgreSQL `DATABASE_URL`, exact hosts and `DEBUG=False` in the target environment. |
| CSRF 403 | Use the exact trusted HTTPS origin and token; do not disable middleware. |
| HTTP redirect locally | Use DEBUG=True only locally; production remains HTTPS-only. |
| Static manifest error | Run collectstatic with the pinned dependencies and inspect the static build output. |
| Old configuration after changing variables | Create a new Preview deployment; do not promote Production as a troubleshooting shortcut. |

## Security, backup and rollback

Previously committed database credentials, Django keys and seeded passwords must be
considered compromised. Removing them from current files does not rotate them or erase
Git history. The owner must rotate database credentials and Django keys at their
providers, reset/disable exposed default accounts through an authorized process,
review access logs, and coordinate secret-store updates. Key rotation invalidates
existing sessions; plan and communicate it. Do not reuse an exposed key as fallback.
Production must use least-privilege database roles and independently reviewed access.

Keep verified backups encrypted outside Git and document restoration ownership.
If this PR is unmerged, closing it leaves Production unchanged. After approval and
release, application rollback means reverting the repair commit or redeploying a
known-good **sanitized** revision with valid rotated environment variables. Never
restore leaked secrets. Do not reverse the initial migration: it would drop tables.
Database rollback requires a separately approved recovery plan and a verified backup;
restoring a snapshot can lose subsequent writes and needs maintenance coordination.

## Verified status (2026-11-15)

- Production logs contained the reported missing `notes_app_student` relation.
- The pre-fix implementation reproduced an orphan User after profile failure and
  accepted a duplicate registration number in isolated local SQLite.
- Vercel listed no project environment variables at audit time.
- Production database identity/ownership, backups, schema and migrations were **not**
  verified or changed. No claim is made that live registration/login is repaired.
- Python 3.12.16 / Django 5.2.19: **18 tests passed**; `check`, production-mode
  `check --deploy --fail-level WARNING` (settings-only, placeholder DB),
  `makemigrations --check --dry-run`, local SQLite migration rehearsal, collectstatic,
  and actual local WSGI GETs for registration, login and a static SVG passed.
- Preview functional verification is **blocked** until isolated database access and
  rotated environment variables are configured. See the repair PR for executed
  local test results. A READY build alone is not functional acceptance.
