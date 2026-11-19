# Authentication and dispatch demo

LifeLane is a SUMO-only academic simulation. A siren detection never changes a signal by itself: a registered or temporarily verified ambulance must submit a route-selected request, then a dispatcher authorizes simulation priority.

On first backend startup, a simulation dispatcher account is created from environment variables (change these outside a local demo): `DEMO_ADMIN_USERNAME=dispatcher` and `DEMO_ADMIN_PASSWORD=LifeLaneDemo!2026`. Set a long, unique `AUTH_SECRET` before deployment.

## Password recovery

LifeLane does not store verified user email addresses and SMTP is not configured, so public recovery cannot send email. Ambulance users must contact LifeLane management. An authenticated `ADMIN` can create a single-use, 30-minute reset link for a staff account; creation is audit logged. Set `AUTH_SHOW_RESET_LINKS=true` only in development to include that link in the API response. In production, share the generated link through an approved staff channel. Relevant environment variables are `AUTH_SECRET`, `AUTH_TOKEN_TTL_MINUTES`, and `AUTH_SHOW_RESET_LINKS`; there are currently no SMTP environment variables because email delivery is not implemented.

The database startup migration adds contact and vehicle fields to `ambulances`, route-verification fields to `requests`, and creates `users`, `auth_sessions`, and `temporary_verifications`. It is non-destructive for the existing SQLite database.

Primary API additions:

- `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`
- `POST /api/ambulances/register` — issues a LifeLane ID, ambulance account, and bearer token
- `POST /api/temporary-verifications` and `/confirm` — 10-minute simulation verification
- `GET /api/routes/options`, `POST /api/requests/{id}/authorize-priority`

Run the backend with `./.venv/Scripts/python.exe -m uvicorn backend.app:app --reload` and the frontend with `cd frontend; npm.cmd run dev`.
