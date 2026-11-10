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
| POST | `/auth/register` | Create an account | Anyone |
| POST | `/auth/login` | Log in and receive a token | Anyone |
| GET | `/auth/me` | Show the logged-in account | Logged-in user |
| GET | `/gpus` | List all GPUs | Logged-in user |
| GET | `/gpus/search?q=keyword` | Search GPUs by keyword | Logged-in user |
| GET | `/gpus/{gpu_id}` | Get one GPU | Logged-in user |
| POST | `/gpus` | Add a GPU | Admin |
| PUT | `/gpus/{gpu_id}` | Update a GPU | Admin |
| DELETE | `/gpus/{gpu_id}` | Delete a GPU | Admin |

Protected requests need the header `Authorization: Bearer <access_token>`. The token comes from `POST /auth/login` and lasts 8 hours.

New accounts get the role `user`. To make an admin, open the `users` table in Supabase, change that account's `role` to `admin`, and log in again.

## Files

| File | Purpose |
| --- | --- |
| `index.py` | FastAPI app and endpoints |
| `models.py` | Pydantic models that validate GPU and account data |
| `database.py` | Supabase connection and queries |
| `auth.py` | Password hashing and login tokens |
| `config.py` | Reads settings from environment variables |
| `supabase/schema.sql` | Creates the `gpus` table |
| `supabase/seed.sql` | Loads the 46 original GPUs |
| `supabase/users.sql` | Creates the `users` table |
| `tests/` | Automated tests |

## Setup

1. Create a Supabase project. In the SQL Editor, run `supabase/schema.sql`, then `supabase/seed.sql`, then `supabase/users.sql`.
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
| `CORS_ORIGINS` | Websites allowed to call the API (default `*`) |

On Vercel, set the same names under Settings → Environment Variables.

## Tests

The tests use a simulated database, so they never change the real one.

```
python -m pip install -r requirements-dev.txt
python -m pytest
```
