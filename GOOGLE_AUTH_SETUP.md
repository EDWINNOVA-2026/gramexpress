# Google Auth Setup For GramExpress

This project uses Google Identity Services on the frontend and expects a Google OAuth web client ID in the Django environment.

The app reads this value from:

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

That variable is loaded in [gramexpress/settings.py](./gramexpress/settings.py).

## What You Need

- A Google account with access to Google Cloud Console
- Your local and production site URLs
- Access to edit this project's `.env`

## Step 1: Open Google Cloud Console

1. Go to `https://console.cloud.google.com/`
2. Sign in with your Google account
3. Create a new project or select an existing project for GramExpress

## Step 2: Configure Google Auth Branding

1. In Google Cloud Console, open `Google Auth Platform`
2. Open the `Branding` section
3. Fill these fields:
   - App name: `GramExpress`
   - User support email: your email
   - App logo: optional
   - Application home page: your public app URL
   - Application privacy policy link: your privacy-policy URL
   - Authorized domains: add your production domain
4. Save the branding configuration

Notes:

- If you only test locally, branding can still be created first and refined later.
- Your app name on the consent screen should match the product name shown in the site UI.

## Step 3: Create the OAuth Client

1. In `Google Auth Platform`, open `Clients`
2. Click `Create client`
3. Choose `Web application`
4. Set a name like `GramExpress Web`

## Step 4: Add Authorized JavaScript Origins

Add the exact origins where the site runs.

For local development:

```text
http://localhost:8000
http://127.0.0.1:8000
```

For production, add your real domain, for example:

```text
https://gramexpress.example.com
```

Important rules:

- Add only the origin, not the full path
- Do not add `/auth/google/`
- Do not add trailing routes like `/login/`
- If you use a custom port, include it

Examples:

- Correct: `http://localhost:8000`
- Correct: `https://gramexpress.example.com`
- Wrong: `http://localhost:8000/auth/google/`

## Step 5: Add Authorized Redirect URIs

GramExpress is currently using Google Identity Services in redirect mode.

That means Google sends the credential directly to this Django endpoint:

```text
/auth/google/
```

From the codebase:

- Route: [core/urls.py](./core/urls.py)
- Frontend redirect target: [templates/core/base.html](./templates/core/base.html)

Add the exact redirect URIs below.

For local development:

```text
http://localhost:8000/auth/google/
http://127.0.0.1:8000/auth/google/
```

For your current production site:

```text
https://gramexpress.pythonanywhere.com/auth/google/
```

Important rules:

- The path must match exactly
- Keep the trailing slash
- Use HTTPS for production
- If you use another live domain later, add that full redirect URI too

Examples:

- Correct: `https://gramexpress.pythonanywhere.com/auth/google/`
- Wrong: `https://gramexpress.pythonanywhere.com/auth/google`
- Wrong: `https://gramexpress.pythonanywhere.com/auth/login/`
- Wrong: `https://gramexpress.pythonanywhere.com/`

## Step 6: Copy The Client ID

After creating the client, Google gives you a client ID that looks like this:

```text
123456789012-abcdefghijklmnopqrstuvwxyz.apps.googleusercontent.com
```

Copy that value.

## Step 7: Put It In `.env`

Open your `.env` file and add:

```env
GOOGLE_CLIENT_ID=123456789012-abcdefghijklmnopqrstuvwxyz.apps.googleusercontent.com
```

If you also want PWA install behavior enabled locally, make sure this is present too:

```env
PWA_ENABLED=true
```

## Step 8: Restart Django

Restart the app after changing `.env`.

If you run Django with:

```bash
venv/bin/python manage.py runserver
```

stop it and start it again.

## Step 9: Verify It Works

1. Open the login page
2. Confirm the `Continue with Google` button is visible
3. Try a Google account that already exists in the system by email
4. Confirm it logs in directly
5. Try a Google account that does not exist yet
6. Confirm it goes to role selection
7. Finish customer, store, or rider onboarding without OTP

## Common Errors

### `Google sign-in client ID does not match this app.`

Usually means the client ID in `.env` does not match the one used to generate the credential.

### `origin_mismatch`

Usually means your site origin is missing in Google Cloud Console.

Check that you added:

- `http://localhost:8000` for local
- your exact HTTPS production domain for live

### `Error 400: redirect_uri_mismatch`

Usually means the redirect URI was not added in the OAuth client.

For the current GramExpress deployment, add this exact value:

```text
https://gramexpress.pythonanywhere.com/auth/google/
```

For local development, also add:

```text
http://localhost:8000/auth/google/
http://127.0.0.1:8000/auth/google/
```

### Google button is disabled

Usually means:

- `GOOGLE_CLIENT_ID` is missing
- Django was not restarted after updating `.env`

## Official References

- Google Identity web setup:
  `https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid`
- Manage OAuth clients:
  `https://support.google.com/cloud/answer/15549257`
- App branding help:
  `https://support.google.com/cloud/answer/13804963`
