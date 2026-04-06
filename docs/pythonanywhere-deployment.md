# PythonAnywhere Deployment Guide

This guide is for deploying GramExpress on PythonAnywhere with:

- SQLite as the database
- GitHub as the source of truth for code changes
- `.env` on the server for secrets and deployment settings

The project already uses SQLite by default in [gramexpress/settings.py](../gramexpress/settings.py), and `db.sqlite3` is ignored by git in [`.gitignore`](../.gitignore), which is exactly what we want for a simple PythonAnywhere deployment.

## At First: Use GitHub As The Main Workflow

Use this workflow from the start:

1. Make code changes locally.
2. Commit and push them to GitHub.
3. On PythonAnywhere, pull the latest code from GitHub.
4. Run migrations if needed.
5. Run `collectstatic`.
6. Reload the web app.

That keeps:

- code in GitHub
- production database on PythonAnywhere
- secrets only in `.env` on PythonAnywhere

Important:

- Do not commit your production `.env`
- Do not commit your production `db.sqlite3`
- Do not edit production code directly unless absolutely necessary

## Why SQLite Is Fine Here

This project uses:

```python
'ENGINE': 'django.db.backends.sqlite3'
```

with the database file at:

```text
<project-root>/db.sqlite3
```

For a small demo or low-traffic app on PythonAnywhere, SQLite is the simplest option.

Tradeoff:

- good for simple deployments
- not ideal for high write volume or heavy concurrency

## 1. Create The PythonAnywhere Web App

1. Log in to PythonAnywhere.
2. Open the `Web` tab.
3. Click `Add a new web app`.
4. Choose your domain.
5. Choose `Manual configuration`.
6. Select the Python version you want.

Use the same major Python version as your local environment if possible.

## 2. Open A Bash Console

In PythonAnywhere:

1. Open the `Consoles` tab.
2. Start a `Bash` console.

## 3. Clone The Repo From GitHub

From the PythonAnywhere Bash console:

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

If the repo is public, that is enough.

If the repo is private, use one of the methods below.

## 3A. Private Repo Option 1: SSH Deploy Key

This is the cleanest option if PythonAnywhere should only read from one private repo.

On PythonAnywhere:

```bash
ssh-keygen -t ed25519 -C "pythonanywhere-gramexpress" -f ~/.ssh/gramexpress_github -N ""
cat ~/.ssh/gramexpress_github.pub
```

Copy the printed public key.

In GitHub:

1. Open your private repository.
2. Go to `Settings` -> `Deploy keys`.
3. Click `Add deploy key`.
4. Title it something like `PythonAnywhere GramExpress`.
5. Paste the public key.
6. Keep `Allow write access` off unless you truly need the server to push.
7. Save.

Then on PythonAnywhere, add an SSH config:

```bash
nano ~/.ssh/config
```

Paste:

```sshconfig
Host github-gramexpress
  HostName github.com
  User git
  IdentityFile ~/.ssh/gramexpress_github
  IdentitiesOnly yes
```

Save the file, then test:

```bash
ssh -T github-gramexpress
```

Then clone with:

```bash
cd ~
git clone git@github-gramexpress:YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

If you already cloned with HTTPS and want to switch to SSH later:

```bash
git remote set-url origin git@github-gramexpress:YOUR_USERNAME/YOUR_REPO.git
```

## 3B. Private Repo Option 2: HTTPS With GitHub Token

Use this if you do not want to manage SSH keys.

1. In GitHub, create a personal access token with repo read access.
2. Clone using HTTPS:

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

3. When Git asks for credentials:
   - Username: your GitHub username
   - Password: your GitHub token

Important:

- Do not put the token directly inside this deployment guide or commit it anywhere.
- If PythonAnywhere asks again on every pull, switch to the SSH deploy key option above.

## 4. Create A Virtual Environment

Example:

```bash
python3.12 -m venv ~/.virtualenvs/gramexpress-venv
source ~/.virtualenvs/gramexpress-venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

If PythonAnywhere gives you a different Python version, use that version instead.

## 5. Create The Production `.env`

Inside your project directory on PythonAnywhere:

```bash
cp .env.example .env
```

Then edit `.env` and add your real production values.

Recommended minimum:

```env
SECRET_KEY=your-strong-secret-key
DEBUG=false
PWA_ENABLED=true

CSRF_TRUSTED_ORIGINS=https://yourusername.pythonanywhere.com

GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
SITE_URL=https://yourusername.pythonanywhere.com

RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@example.com
EMAIL_HOST_PASSWORD=your-email-app-password
EMAIL_USE_TLS=true
EMAIL_TIMEOUT=20
DEFAULT_FROM_EMAIL=GramExpress <your-email@example.com>

SMS_BACKEND=console
```

If you are deploying the current public site, your CSRF origin would be:

```env
CSRF_TRUSTED_ORIGINS=https://gramexpress.pythonanywhere.com
```

## 6. Run Migrations

From the project directory:

```bash
source ~/.virtualenvs/gramexpress-venv/bin/activate
python manage.py migrate
```

This creates the production SQLite database on the server.

Because `db.sqlite3` is gitignored, it stays on PythonAnywhere and is not mixed with GitHub code changes.

## 7. Collect Static Files

Run:

```bash
python manage.py collectstatic --noinput
```

The project writes collected files to:

```text
<project-root>/staticfiles
```

## 8. Configure The WSGI File

Go to the `Web` tab on PythonAnywhere and open the WSGI configuration file.

Typical path:

```text
/var/www/yourusername_pythonanywhere_com_wsgi.py
```

Use a configuration like this:

```python
import os
import sys

path = '/home/yourusername/YOUR_REPO'
if path not in sys.path:
    sys.path.append(path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gramexpress.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

Replace:

- `yourusername`
- `YOUR_REPO`

with your real values.

## 9. Set The Virtualenv In The Web Tab

In PythonAnywhere `Web` tab:

- set the virtualenv path to:

```text
/home/yourusername/.virtualenvs/gramexpress-venv
```

## 10. Configure Static And Media Mappings

In the PythonAnywhere `Web` tab, add these mappings.

Static files:

- URL: `/static/`
- Directory: `/home/yourusername/YOUR_REPO/staticfiles`

Media files:

- URL: `/media/`
- Directory: `/home/yourusername/YOUR_REPO/media`

This matches the project settings:

- `STATIC_ROOT = BASE_DIR / 'staticfiles'`
- `MEDIA_ROOT = BASE_DIR / 'media'`

## 11. Reload The Web App

After configuring everything, click `Reload` in the PythonAnywhere `Web` tab.

Then open your site.

## 12. First-Time Checks

After deployment, verify:

1. Login page loads.
2. Google sign-in button is enabled.
3. Static CSS is loading.
4. Admin works.
5. Razorpay keys are loaded.
6. Password reset page opens.
7. PWA manifest loads.

Useful checks:

```text
https://yourdomain/manifest.json
https://yourdomain/auth/login/
```

## 13. Updating The Site From GitHub Later

When you push new code to GitHub, update production like this:

```bash
cd ~/YOUR_REPO
source ~/.virtualenvs/gramexpress-venv/bin/activate
git pull origin main
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

If you used the private-repo SSH deploy-key setup, the same `git pull origin main` command will keep working without prompting for credentials.

Then:

1. go to PythonAnywhere `Web`
2. click `Reload`

## 14. SQLite Safety Notes

Because you are using SQLite:

- keep `db.sqlite3` only on the server
- back it up before risky deploys
- do not commit it to GitHub

Simple backup command:

```bash
cp db.sqlite3 db.sqlite3.backup
```

## 15. Recommended GitHub Workflow

Use this order for every release:

1. Change code locally
2. Test locally
3. Commit
4. Push to GitHub
5. Pull on PythonAnywhere
6. Run migrate
7. Run collectstatic
8. Reload

## 16. If Something Does Not Work

Check these places:

- PythonAnywhere `Web` tab error log
- PythonAnywhere server log
- your `.env`
- WSGI file path
- static file mapping

Most common problems:

- forgot to reload web app
- missing `.env` value
- wrong virtualenv path
- forgot `collectstatic`
- wrong static/media mapping
- local change was not pushed to GitHub
