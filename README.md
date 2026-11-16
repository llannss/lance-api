# GPU Finder API

A REST API for browsing, searching and managing a catalog of NVIDIA GeForce GPUs.

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3FCF8E?logo=supabase&logoColor=white)

## About

The API serves RTX, GTX, and GT graphics card specifications as JSON. The GPU Finder website is a separate project that calls this API.

Version 2 stores the GPU catalog and the user accounts in a Supabase (PostgreSQL) database instead of a hardcoded Python list. Users sign up and log in before they can browse.

## API endpoints

| Method | Endpoint | Purpose | Who can use it |
| --- | --- | --- | --- |
| GET | `/` | API information | Anyone |
| GET | `/health` | Check the API and database | Anyone |
| POST | `/auth/register` | Create an account and email a confirmation link | Anyone |
| POST | `/auth/verify` | Confirm the email with the link's token | Anyone with the link |
| POST | `/auth/resend-verification` | Send a new confirmation link | Anyone |
| POST | `/auth/login` | Log in: sets the session cookie and returns a token | Anyone |
| POST | `/auth/logout` | End the session in this browser | Anyone |
| POST | `/auth/logout-all` | End every session of the account | Logged-in user |
| POST | `/auth/forgot-password` | Email a password reset link | Anyone |
| POST | `/auth/reset-password` | Set a new password with the link's token | Anyone with the link |
| GET | `/auth/me` | Show the logged-in account | Logged-in user |
| POST | `/chat` | Ask the Gemini GPU assistant | Logged-in user |
| GET | `/gpus` | List all GPUs | Logged-in user |
| GET | `/gpus/search?q=keyword` | Search GPUs by keyword | Logged-in user |
| GET | `/gpus/{gpu_id}` | Get one GPU | Logged-in user |
| POST | `/gpus` | Add a GPU | Admin |
| PUT | `/gpus/{gpu_id}` | Update a GPU | Admin |
| DELETE | `/gpus/{gpu_id}` | Delete a GPU | Admin |

Logging in sets an HttpOnly, Secure, `SameSite=Strict` cookie named `gpu_session` that lasts 8 hours; the website uses it. API clients such as Swagger can send `Authorization: Bearer <access_token>` instead, using the token from the login response. Writes made with the cookie must also send the header `X-Requested-With`, which other websites cannot add.

New accounts get the role `user` and must confirm their email before they can log in. To make an admin, open the `users` table in Supabase and change that account's `role` to `admin`. The change takes effect on the next request, because every request re-reads the account.

### Sign-in protections

| Protection | Rule |
| --- | --- |
| Account lockout | 5 wrong passwords lock the account for 15 minutes |
| Login limit | 20 attempts per IP address every 15 minutes |
| Sign-up limit | 5 accounts per IP address per hour |
| Email links | 3 per address and 10 per IP address per hour; verify links last 24 hours, reset links 30 minutes, each works once |
| Sign out everywhere | Raises the account's `token_version`; a password reset does the same |
| Chat | 10 messages a minute per account, 500 a day for the whole site |

Limits are counted in the database (`hit_rate_limit`), so every Vercel instance shares them.

## Files

| File | Purpose |
| --- | --- |
| `index.py` | FastAPI app and endpoints |
| `models.py` | Pydantic models that validate GPU and account data |
| `database.py` | Supabase connection and queries |
| `auth.py` | Password hashing, login tokens, email link secrets |
| `security.py` | Who is calling (cookie or Bearer), admin check, rate limits |
| `chat.py` | `POST /chat`, the Gemini assistant |
| `mailer.py` | Sends verification and reset emails through Gmail |
| `config.py` | Reads settings from environment variables |
| `supabase/schema.sql` | Creates the `gpus` table |
| `supabase/seed.sql` | Loads the 46 original GPUs |
| `supabase/users.sql` | Creates the `users` table |
| `supabase/auth_upgrade.sql` | Adds email verification, lockout, sign-out everywhere, email links and rate limits |
| `tests/` | Automated tests |

## Setup

1. Create a Supabase project. In the SQL Editor, run `supabase/schema.sql`, then `supabase/seed.sql`, then `supabase/users.sql`, then `supabase/auth_upgrade.sql`.
2. Copy `.env.example` to `.env` and fill in your values. Git ignores `.env`.
3. Install the packages and start the API:

   ```
   python -m pip install -r requirements.txt
   python -m uvicorn index:app --host 127.0.0.1 --port 8000
   ```

4. Open http://127.0.0.1:8000/docs.

## Environment variables

| Name | Purpose |
| --- | --- |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SECRET_KEY` | Private server key for Supabase |
| `AUTH_SECRET` | Random text of at least 32 characters used to sign login tokens |
| `SITE_URL` | The website's address, used in emailed links |
| `GMAIL_ADDRESS` | Gmail account that sends account emails |
| `GMAIL_APP_PASSWORD` | That account's App Password (needs 2-Step Verification) |
| `GEMINI_API_KEY` | Google AI Studio key for `/chat` |
| `GEMINI_MODEL` | Gemini model name (default `gemini-3.1-flash-lite`) |
| `CORS_ORIGINS` | Other browser origins allowed to call the API directly (default: none) |

On Vercel, set the same names under Settings → Environment Variables.

## Tests

The tests use a simulated database, so they never change the real one.

```
python -m pip install -r requirements-dev.txt
python -m pytest
```
