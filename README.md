# GramExpress Django Demo

GramExpress is a mobile-first Django demo for a hyperlocal delivery platform with:

- unified sign-in with phone or email
- mobile OTP verification during registration
- email OTP verification when users sign in with email
- Google sign-in hook for existing accounts
- customer, store, and rider dashboards
- multi-store cart checkout
- installable PWA shell

## Quick start

1. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

2. Run migrations:

```bash
python manage.py migrate
```

3. Seed demo data:

```bash
python manage.py seed_demo
```

4. Start the server:

```bash
python manage.py runserver 0.0.0.0:8000
```

Open `http://127.0.0.1:8000`.

## Environment

Copy `.env.example` to `.env` and fill in the integrations you want:

- `GOOGLE_CLIENT_ID` for Google sign-in
- `EMAIL_*` settings for real email OTP delivery
- `SMS_BACKEND` plus Twilio credentials for live SMS OTP delivery
- `GOOGLE_MAPS_*` keys for richer map embeds

If you keep:

```env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
SMS_BACKEND=console
```

email and SMS OTPs will stay in local/demo mode.

## Demo access

- Admin: `admin / admin123`
- Customer phone: `+919188843299`
- Store phone: `+919900010101`
- Rider phone: `+919900011111`
- Shared password for customer, store, and rider: `demo12345`

## Supporting docs

- PythonAnywhere deployment: `PYTHONANYWHERE_DEPLOYMENT.md`
- setup notes: `THIRD_PARTY_SETUP.txt`
- Google auth setup: `GOOGLE_AUTH_SETUP.md`
- Razorpay setup: `RAZORPAY_SETUP.md`
- implementation plan: `implementation.md`
