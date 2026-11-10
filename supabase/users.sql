-- GPU Finder API: user accounts for sign-up and login
-- Run this in the Supabase SQL Editor after schema.sql and seed.sql.

create table if not exists public.users (
    id bigint generated always as identity (maxvalue 9007199254740991) primary key,

    -- Stored in lowercase so the same address cannot sign up twice.
    email text not null
        check (
            char_length(email) between 3 and 254
            and email = lower(email)
            and position('@' in email) > 1
        ),

    -- Never the password itself, only a salted hash of it.
    password_hash text not null
        check (char_length(password_hash) between 20 and 300),

    -- 'user' can browse GPUs. 'admin' can also add, edit and delete them.
    role text not null default 'user'
        check (role in ('user', 'admin')),

    created_at timestamptz not null default now()
);

create unique index if not exists users_email_key on public.users (email);

-- Security: browsers cannot read or change the table directly.
-- The backend can only read accounts and add new ones.
alter table public.users enable row level security;
revoke all on table public.users from anon, authenticated, service_role;
grant select, insert on table public.users to service_role;
