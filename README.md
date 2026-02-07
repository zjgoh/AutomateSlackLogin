# Slack Auto-Login

Automate signing in to Slack (e.g. after daily session timeout). Uses Selenium with **auto-detected ChromeDriver** and **TOTP** for 2FA so the script can generate the code from your secret key.

## Quick start

1. **Create `.env` from the example**
   ```powershell
   copy .env.example and create another .env
   ```
   Edit `.env` and set:
   - `SLACK_EMAIL` – your Slack email
   - `SLACK_PASSWORD` – your Slack password
   - `SLACK_TOTP_SECRET` – your 2FA secret key (base32, from Slack’s “Set up authenticator app” → “Enter key manually”)

2. **Run Slack_Login.bat**
   Double‑click **Slack_Login.bat**. It runs everything step by step:
   - **Check if Python exists** (looks for `python`, `py`, or Python in standard install folders).
   - **If Python is not installed:** runs `library\Install_Python.bat` to install Python 3.12 via winget, then **automatically relaunches** Slack_Login in a new window so the rest runs without you doing anything else.
   - **If Python is found:** upgrades pip → installs dependencies → runs the Slack auto-login script.

   You only need to run **Slack_Login.bat** once; no need to rerun manually after Python is installed.

3. **Manual run (optional)**  
   If you prefer to run from a terminal:
   ```powershell
   pip install -r library\requirements.txt
   python library\slack_auto_login.py
   ```
   If `python` is not in your PATH, use `py -3` instead of `python`.

4. **2FA**  
   If `SLACK_TOTP_SECRET` is set, the script generates the current 6‑digit code and fills it in. If not set, the script waits and you can enter the code manually.

---

## Getting your TOTP secret (2FA key)

- In Slack: **Settings** → **Security** → **Two-Factor Authentication** → **Set up authenticator app** (or **Manage** if already set up).
- Choose **“Enter key manually”** (or similar) and copy the **secret key** (base32 string, often with spaces).
- Paste it into `.env` as `SLACK_TOTP_SECRET=`. You can leave or remove spaces; the script normalizes it.

---

## Env reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SLACK_EMAIL` | Yes | Slack sign-in email |
| `SLACK_PASSWORD` | Yes | Slack password |
| `SLACK_TOTP_SECRET` | For auto 2FA | Base32 TOTP secret from Slack 2FA setup |
| `SLACK_SIGNIN_URL` | No | Slack sign-in URL; set if your workspace uses a different one |
---

## After login

The script leaves the browser open so you can use Slack. Press Enter in the terminal when you want to close it.

If your company uses a different sign-in URL, set `SLACK_SIGNIN_URL` in `.env`.
