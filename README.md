# GramExpress

**Live Site:** https://gramexpress.pythonanywhere.com

GramExpress is a mobile-first Django platform for hyperlocal commerce and last-mile delivery. It is designed around three connected user journeys, customers placing orders, shop owners managing local inventory and fulfillment, and riders handling delivery operations, inside one server-rendered web application with progressive web app support.

## Overview

GramExpress brings the core workflows of a neighbourhood delivery product into a single codebase:

- Customer discovery, cart, checkout, and order tracking
- Shop onboarding, catalog management, and order handling
- Rider onboarding, availability, delivery progress, and earnings views
- OTP-assisted authentication across phone and email flows
- Razorpay-backed payment handling and notification-driven updates

The project is built as a practical Django application rather than a disconnected prototype. It includes seeded demo data, integration hooks for real-world services, and deployment documentation for the live PythonAnywhere environment.

## Product Capabilities

### Customer Experience

- Sign in with phone or email
- Complete OTP verification flows for secure access
- Browse stores and products
- Add items to cart and review checkout
- Track order progress after placement
- View notifications, profile data, and order history

### Shop Owner Experience

- Maintain store and profile information
- Manage product listings and stock
- Monitor incoming orders and fulfillment status
- Access a dedicated store dashboard and order workflow

### Rider Experience

- Maintain rider profile and availability
- View assigned deliveries and completed orders
- Track earnings and rider-specific operational status

### Platform Features

- Google sign-in support for eligible accounts
- Session-based cart and multi-step checkout flow
- COD and Razorpay payment support
- Role-aware dashboards and notification center
- Installable PWA shell for mobile-friendly usage

## Technology Stack

- **Backend:** Django 5.x
- **Language:** Python 3.11
- **Database:** SQLite
- **Frontend:** Django templates with custom CSS
- **Authentication:** Django auth with custom role/profile mapping
- **Integrations:** Google Identity Services, Razorpay, email OTP, SMS OTP
- **Deployment:** PythonAnywhere

## Quick Start

1. Install dependencies

```bash
python -m pip install -r requirements.txt
```

2. Configure environment variables

```bash
cp .env.example .env
```

3. Apply database migrations

```bash
python manage.py migrate
```

4. Seed demo data

```bash
python manage.py seed_demo
```

5. Start the development server

```bash
python manage.py runserver 0.0.0.0:8000
```

Open `http://127.0.0.1:8000`.

## Environment Configuration

The project reads configuration from `.env`. The most commonly used settings are:

- `SECRET_KEY`
- `DEBUG`
- `SITE_URL`
- `GOOGLE_CLIENT_ID`
- `EMAIL_*`
- `SMS_BACKEND`, `SMS_FROM`, `TWILIO_*`
- `GOOGLE_MAPS_BROWSER_API_KEY`
- `GOOGLE_MAPS_EMBED_API_KEY`
- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `RAZORPAY_WEBHOOK_SECRET`

For local demo mode, you can keep OTP delivery in the console:

```env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
SMS_BACKEND=console
```

## Demo Accounts

Use the seeded credentials below after running `python manage.py seed_demo`:

- Admin: `admin / admin123`
- Customer phone: `+919188843299`
- Store phone: `+919900010101`
- Rider phone: `+919900011111`
- Shared password for customer, store, and rider: `demo12345`

## Project Structure

```text
gramexpress/
├── core/                     # Business logic, models, forms, views, urls
├── gramexpress/              # Django project settings and entrypoints
├── templates/core/           # Server-rendered UI templates
├── static/core/              # Styles, icons, and static assets
├── docs/                     # Deployment, integration, and project docs
├── manage.py
└── requirements.txt
```

## Documentation

All supporting documentation is organized in [`docs/`](docs/README.md).

- Documentation index: [`docs/README.md`](docs/README.md)
- Deployment guide: [`docs/pythonanywhere-deployment.md`](docs/pythonanywhere-deployment.md)
- Third-party setup: [`docs/third-party-setup.md`](docs/third-party-setup.md)
- Google authentication setup: [`docs/google-auth-setup.md`](docs/google-auth-setup.md)
- Razorpay setup: [`docs/razorpay-setup.md`](docs/razorpay-setup.md)
- Implementation guide: [`docs/implementation-guide.md`](docs/implementation-guide.md)
- Full technical documentation source: [`docs/project-documentation.tex`](docs/project-documentation.tex)
- Full technical documentation PDF: [`docs/project-documentation.pdf`](docs/project-documentation.pdf)

## Deployment

The current public deployment runs on PythonAnywhere:

- Live application: https://gramexpress.pythonanywhere.com
- Deployment reference: [`docs/pythonanywhere-deployment.md`](docs/pythonanywhere-deployment.md)

## Development Notes

- The app uses SQLite by default for simple local setup and lightweight deployment
- Demo data is available through the custom `seed_demo` management command
- External services can be enabled incrementally without changing the local development workflow


This will be converted to React Native 
