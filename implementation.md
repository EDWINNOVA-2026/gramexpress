# GramExpress Implementation Guide

## Overview

GramExpress is a mobile-first Django application for a hyperlocal delivery workflow with three primary user roles:

- Customer
- Store owner
- Rider

The project is implemented as a server-rendered Django web app with a PWA shell, SQLite for local development, role-aware dashboards, OTP-assisted authentication flows, checkout, order tracking, and notifications.

This document reflects the code that currently exists in this repository.

## Current Stack

- Backend: Django 5.x
- Database: SQLite
- Templates: Django templates
- Styling: custom CSS in `static/core/styles.css`
- Auth: Django auth plus custom role/profile mapping
- OTP delivery:
  - Email via Django email backend
  - SMS via console backend or Twilio
- PWA support:
  - `manifest.json`
  - `service-worker.js`

## Project Structure

```text
gramexpress/
├── core/
│   ├── admin.py
│   ├── forms.py
│   ├── models.py
│   ├── tests.py
│   ├── urls.py
│   ├── views.py
│   ├── migrations/
│   └── management/commands/seed_demo.py
├── gramexpress/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── templates/core/
├── static/core/
├── manage.py
├── requirements.txt
└── README.md
```

## Implemented Product Scope

### 1. Authentication

The app supports:

- Login with phone or email plus password
- Email OTP verification for email-based login
- Mobile OTP verification during registration
- Google sign-in verification hook for existing accounts
- Logout

Authentication is backed by Django users plus role-specific profile models. The code maps an account to a role using profile records instead of relying only on Django groups.

### 2. Multi-Role Profiles

Implemented profile models:

- `CustomerProfile`
- `ShopOwnerProfile`
- `RiderProfile`

Each role has its own onboarding data and dashboard behavior. Store owners and riders also carry approval state for admin moderation.

### 3. Store and Catalog

Implemented store/catalog entities:

- `Shop`
- `Product`

Features already present:

- Store owner profile linked to one or more shops
- Shop approval state
- Product create/update form support in the dashboard flow
- Product stock tracking
- Simple product metadata such as category, unit, color, tag, and image URL

### 4. Orders and Checkout

Implemented order entities:

- `Order`
- `OrderItem`

Customer checkout supports:

- Session-based cart
- Multi-item order creation
- Review step before confirmation
- Stock re-validation
- Delivery fee and total calculation
- Rider assignment from available approved riders
- COD and Razorpay payment method options at the data/model layer

Order lifecycle states:

- `pending`
- `confirmed`
- `packed`
- `out_for_delivery`
- `delivered`
- `cancelled`

Additional implemented order features:

- Customer notes
- Cancellation reason
- Cancellation role tracking
- Customer rating and review
- Store rating and review
- Delivery completion timestamp
- Customer OTP field for delivery handoff

### 5. Notifications

Implemented notification center supports:

- Role-aware notification listing
- Notification grouping by recency
- Open-to-destination behavior
- Mark-all-read flow
- Notification type classification:
  - order
  - store
  - rider
  - payment
  - promo
  - system

### 6. PWA Shell

The app exposes:

- App manifest endpoint
- Service worker endpoint
- Installable shell behavior for mobile-friendly use

## Data Model Summary

### Core reference enums

Defined in `core/models.py`:

- `ApprovalStatus`
- `ShopType`
- `VehicleType`
- `OrderStatus`
- `PaymentMethod`
- `PaymentStatus`
- `RoleType`
- `NotificationType`
- `OtpPurpose`
- `OtpChannel`

### Main models

#### CustomerProfile

Stores:

- linked user
- name
- phone
- email
- language
- address
- pincode
- latitude/longitude

#### ShopOwnerProfile

Stores:

- linked user
- name
- phone
- email
- approval status

#### RiderProfile

Stores:

- linked user
- name
- phone
- email
- age
- vehicle type
- approval status
- availability
- service radius
- rating
- coordinates
- optional image/file

#### Shop

Stores:

- owner
- shop name and slug
- shop type
- area and address
- district and pincode
- description and offer
- image URL/file
- open state
- approval state
- rating
- coordinates

#### Product

Stores:

- shop
- name and subtitle
- category
- unit
- price
- stock
- image URL
- color
- merchandising tag

#### Order

Stores:

- customer
- shop
- rider
- status
- payment method/status
- totals and delivery fee
- delivery address
- customer OTP
- notes
- cancellation metadata
- ratings/reviews
- delivered timestamp

#### OrderItem

Stores:

- order
- product
- quantity
- unit price

#### Notification

Stores:

- optional customer/shop_owner/rider target
- optional order reference
- notification type
- title/body
- read state

#### EmailOtpToken

Legacy/earlier email OTP model retained in codebase.

#### AuthOtpToken

Primary current OTP model used for:

- registration OTP
- login email OTP

Stores:

- user
- role
- purpose
- channel
- email
- phone
- code
- expiry
- used flag
- metadata JSON

## Main User Flows

### 1. Registration Flow

Route: `/auth/register/`

Flow:

1. User selects account type
2. User fills role-specific registration form
3. System validates required fields for that role
4. System generates mobile OTP
5. User verifies OTP
6. Django user and matching role profile are created or updated
7. Initial notification is created
8. User is logged in and redirected to the appropriate dashboard

### 2. Login Flow

Route: `/auth/login/`

Flow:

1. User enters phone/email and password
2. System resolves role identity from profile data
3. If login is phone-based and credentials are valid, sign-in completes
4. If login is email-based and credentials are valid, an email OTP is generated
5. User verifies OTP
6. Session login completes

### 3. Customer Shopping Flow

Customer routes:

- `/customer/dashboard/`
- `/customer/checkout/`
- `/customer/checkout/success/`
- `/orders/<id>/`
- `/orders/<id>/tracking/`

Flow:

1. Customer browses approved/open stores and products
2. Customer adds products to session cart
3. System validates stock and cart health
4. Customer reviews order
5. Order is created inside a transaction
6. Stock is decremented
7. Available rider may be assigned
8. Notifications are created
9. Customer can later:
   - view details
   - track order
   - cancel eligible orders
   - reorder delivered/cancelled items
   - leave ratings and reviews

### 4. Shop Owner Flow

Routes:

- `/shop/start/`
- `/shop/dashboard/`

Capabilities in current implementation:

- view store dashboard
- inspect store orders
- manage product catalog
- update order status
- submit rider/store-side rating where applicable

### 5. Rider Flow

Routes:

- `/rider/start/`
- `/rider/dashboard/`
- `/rider/location/`

Capabilities in current implementation:

- view assigned or available delivery work
- accept orders
- update rider location
- update delivery status
- participate in final delivery flow

### 6. Notification Flow

Routes:

- `/notifications/`
- `/notifications/mark-all-read/`
- `/notifications/<id>/open/`

Capabilities:

- list notifications for active role
- group by time buckets
- mark notifications read
- open linked order screens

## URL Map

Implemented URL patterns in `core/urls.py` include:

- `/`
- `/auth/login/`
- `/auth/google/`
- `/auth/register/`
- `/auth/email-otp/`
- `/logout/`
- `/notifications/`
- `/orders/<id>/`
- `/orders/<id>/tracking/`
- `/customer/start/`
- `/customer/dashboard/`
- `/customer/cart/add/<product_id>/`
- `/customer/cart/update/<product_id>/`
- `/customer/cart/clear/`
- `/customer/checkout/`
- `/customer/checkout/success/`
- `/customer/order/<id>/cancel/`
- `/customer/order/<id>/reorder/`
- `/customer/order/<id>/rate/`
- `/shop/start/`
- `/shop/dashboard/`
- `/shop/product/<id>/delete/`
- `/shop/order/<id>/status/`
- `/shop/order/<id>/rate/`
- `/rider/start/`
- `/rider/dashboard/`
- `/rider/location/`
- `/rider/order/<id>/accept/`
- `/rider/order/<id>/status/`
- `/manifest.json`
- `/service-worker.js`

## Forms Implemented

Defined in `core/forms.py`:

- `LoginForm`
- `RoleLoginForm`
- `LoginOtpVerifyForm`
- `EmailOtpRequestForm`
- `EmailOtpVerifyForm`
- `UnifiedRegistrationForm`
- `CustomerOnboardingForm`
- `CustomerProfileForm`
- `ShopOwnerOnboardingForm`
- `RiderOnboardingForm`
- `ShopUpdateForm`
- `ProductForm`
- `CustomerOrderMetaForm`
- `RatingForm`
- `StoreRatingForm`
- `RiderLocationForm`

The shared `BaseStyledForm` applies the default input styling and common HTML attributes for mobile-friendly usage.

## Admin and Moderation

The project includes Django admin integration and approval flows for:

- pending stores
- pending riders

Admin/demo user:

- username: `admin`
- password: `admin123`

## Demo Seed Data

The command `python manage.py seed_demo` creates:

- admin user
- customer user/profile
- store owner user/profile
- rider user/profile
- one approved shop
- sample products
- sample order
- notifications for each role

Demo credentials from the current repo:

- Admin: `admin / admin123`
- Customer phone: `+919188843299`
- Store phone: `+919900010101`
- Rider phone: `+919900011111`
- Shared password: `demo12345`

## Configuration

Important settings in `gramexpress/settings.py`:

- `DEBUG`
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- SQLite database path
- static/media settings
- email backend settings
- OTP expiry settings
- SMS backend selection
- Twilio credentials
- Google Maps keys
- Google client ID
- Razorpay keys

### Environment variables

The code currently reads:

- `SECRET_KEY`
- `DEBUG`
- `GRAMEXPRESS_APP_NAME`
- `GOOGLE_MAPS_BROWSER_API_KEY`
- `GOOGLE_MAPS_EMBED_API_KEY`
- `GOOGLE_CLIENT_ID`
- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `DEFAULT_FROM_EMAIL`
- `EMAIL_BACKEND`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`
- `OTP_EXPIRY_MINUTES`
- `SMS_BACKEND`
- `SMS_FROM`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`

## Local Setup

### Install

```bash
python -m pip install -r requirements.txt
```

### Migrate

```bash
python manage.py migrate
```

### Seed demo data

```bash
python manage.py seed_demo
```

### Run server

```bash
python manage.py runserver 0.0.0.0:8000
```

Open:

```text
http://127.0.0.1:8000
```

## Database and Migration Notes

The project uses Django migrations under `core/migrations/`.

Current migration chain:

- `0001_initial`
- `0002_customerprofile_user_order_customer_rating_and_more`
- `0003_authotptoken`
- `0004_order_cancellation_reason_order_cancelled_by_role`
- `0005_notification_notification_type`

If the app raises an insert error related to missing columns, run:

```bash
python manage.py migrate
```

## Testing

The repository includes Django test coverage for key flows in `core/tests.py`, including:

- login page rendering
- registration page rendering
- role-based home redirect
- add-to-cart and checkout
- checkout blocking on stock changes
- notifications page
- order detail and tracking
- cancellation and stock restoration
- reorder flow
- registration OTP flow
- email OTP login flow
- admin approval actions

Run tests with:

```bash
python manage.py test
```

## Current Strengths

- Real end-to-end multi-role flow in one Django app
- Clear separation between auth user and business profiles
- Works well as a demo and prototype
- Covers registration, login, checkout, notifications, and dashboards
- Includes seeded demo content and tests
- Mobile-oriented templates and PWA support

## Current Limitations

The codebase is functional, but several capabilities are still demo-level or partial:

- SQLite is used instead of a production database
- Real payment capture flow is not fully implemented
- Google sign-in is a verification hook, not a full OAuth session integration
- SMS is console-backed by default and only optionally Twilio-backed
- No background worker/queue system
- No websocket-based live tracking
- No full inventory reservation system
- File/media handling is basic
- No REST API or separate React Native frontend in this repo

## Recommended Next Steps

If this project is being extended beyond demo scope, the highest-value next steps are:

1. Move to PostgreSQL for production data integrity and deployment readiness.
2. Add full payment lifecycle integration for Razorpay.
3. Add stronger stock reservation and checkout concurrency protection.
4. Expand admin tooling for approvals, support, refunds, and order oversight.
5. Add audit logging and better observability.
6. Introduce background jobs for OTP delivery, notification fanout, and cleanup.
7. Add deployment configuration for static/media serving and secure secrets.
8. Add API endpoints only if a separate mobile app is planned.

## Summary

GramExpress is currently implemented as a Django-first hyperlocal commerce demo with:

- unified multi-role auth
- OTP-backed registration and email login
- customer/shop/rider dashboards
- cart and checkout
- delivery order lifecycle
- notifications
- installable PWA support
- demo seeding and test coverage

It is a solid working prototype and a good foundation for either a more production-ready Django app or a future API-backed mobile product.
