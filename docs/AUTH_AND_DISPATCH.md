# Authentication and dispatch demo

LifeLane is a SUMO-only academic simulation. A siren detection never changes a signal by itself: a registered or temporarily verified ambulance must submit a route-selected request, then a dispatcher authorizes simulation priority.

On first backend startup, a simulation dispatcher account is created from environment variables (change these outside a local demo): `DEMO_ADMIN_USERNAME=dispatcher` and `DEMO_ADMIN_PASSWORD=LifeLaneDemo!2026`. Set a long, unique `AUTH_SECRET` before deployment.

## Password recovery

Accounts created through ambulance registration now include a registered email address. `POST /api/auth/forgot-password` accepts that email and always returns the same response, whether or not an account exists. For a matching active account, LifeLane creates a 256-bit single-use token, stores only its SHA-256 hash for 15 minutes, and emails a link to `/reset-password`. `POST /api/auth/reset-password` applies the normal password policy and hashing, consumes the token, and revokes every existing session.

Configure `FRONTEND_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, and `SMTP_USE_TLS` in the backend environment. Secrets must never be added to frontend environment files. SMTP is optional during local development: with `EMAIL_DEV_LOG_LINKS=true` (the default), the reset URL is logged by the backend instead. Existing accounts are preserved by the additive nullable `users.email` migration; they need an email assigned before they can use email recovery.

The database startup migration adds contact and vehicle fields to `ambulances`, route-verification fields to `requests`, and creates `users`, `auth_sessions`, and `temporary_verifications`. It is non-destructive for the existing SQLite database.

Primary API additions:

- `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`
- `POST /api/auth/forgot-password`, `POST /api/auth/reset-password`
- `POST /api/ambulances/register` — issues a LifeLane ID, ambulance account, and bearer token
- `POST /api/temporary-verifications` and `/confirm` — 10-minute simulation verification
- `GET /api/routes/options`, `POST /api/requests/{id}/authorize-priority`

Run the backend with `./.venv/Scripts/python.exe -m uvicorn backend.app:app --reload` and the frontend with `cd frontend; npm.cmd run dev`.
