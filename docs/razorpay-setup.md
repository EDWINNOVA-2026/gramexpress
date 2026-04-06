# Razorpay Setup For GramExpress

This project already includes Razorpay checkout, payment verification, payment links, and webhook handling.

The app expects these environment variables:

```env
RAZORPAY_KEY_ID=your_key_id
RAZORPAY_KEY_SECRET=your_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
```

These values are loaded from `.env`.

## What This Project Uses Razorpay For

- Customer online checkout
- KhataBook due payments
- COD online payment links
- Rider settlement QR and payment webhook updates

Relevant code:

- Checkout + Razorpay order creation: [core/views.py](../core/views.py)
- Webhook endpoint route: [core/urls.py](../core/urls.py)

## Step 1: Create Or Log In To Razorpay

1. Go to `https://dashboard.razorpay.com/`
2. Log in or create your Razorpay account
3. Choose `Test Mode` first while developing

## Step 2: Get API Keys

1. In the Razorpay dashboard, open `Settings`
2. Open `API Keys`
3. Click `Generate Key` if needed
4. Copy:
   - `Key ID`
   - `Key Secret`

Important:

- `Key Secret` is server-side only
- Never expose `Key Secret` in frontend code
- This Django app uses `RAZORPAY_KEY_ID` on the frontend checkout and both `RAZORPAY_KEY_ID` plus `RAZORPAY_KEY_SECRET` on the backend

## Step 3: Add Keys To `.env`

Put them in your `.env`:

```env
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxx
RAZORPAY_WEBHOOK_SECRET=choose_a_secret_here
```

## Step 4: Configure The Webhook

This app exposes the webhook at:

```text
/payments/razorpay/webhook/
```

For your PythonAnywhere deployment, the full webhook URL should be:

```text
https://gramexpress.pythonanywhere.com/payments/razorpay/webhook/
```

For local development, if you expose your app with ngrok or a similar tunnel, use your tunnel URL:

```text
https://your-subdomain.ngrok-free.dev/payments/razorpay/webhook/
```

## Step 5: Set The Webhook Secret In Razorpay

1. In Razorpay dashboard, open `Settings`
2. Open `Webhooks`
3. Click `Add New Webhook`
4. Paste your webhook URL
5. Enter a webhook secret
6. Put the same exact value into:

```env
RAZORPAY_WEBHOOK_SECRET=that_same_secret
```

The webhook signature is verified server-side before processing.

## Step 6: Recommended Webhook Events

Enable the events used by this app:

- `payment.captured`
- `payment.failed`
- `order.paid`
- `payment_link.paid`
- `payment_link.cancelled`
- `payment_link.expired`
- `payment_link.partially_paid`
- `qr_code.credited`

These are handled in the Razorpay webhook flow in the backend.

## Step 7: Restart Django

After updating `.env`, restart the Django process.

Example:

```bash
venv/bin/python manage.py runserver
```

## Step 8: Test In Razorpay Test Mode

1. Start the app
2. Log in as a customer
3. Add items to cart
4. Choose Razorpay in checkout
5. Complete a test payment
6. Confirm the app returns to the success flow

Also test:

- COD online payment link flow
- KhataBook Razorpay payment flow
- Webhook delivery from Razorpay dashboard

## Production Checklist

- Replace `rzp_test_...` keys with live keys
- Use a strong unique `RAZORPAY_WEBHOOK_SECRET`
- Make sure your production domain is HTTPS
- Confirm the webhook URL is publicly reachable
- Rotate any secret that was shared insecurely

## Current Project Note

This repo is already configured to read:

- `RAZORPAY_KEY_ID`
- `RAZORPAY_KEY_SECRET`
- `RAZORPAY_WEBHOOK_SECRET`

from `.env.example` and `.env`.

## Current PythonAnywhere Webhook URL

Use this in Razorpay dashboard for the deployed app:

```text
https://gramexpress.pythonanywhere.com/payments/razorpay/webhook/
```
