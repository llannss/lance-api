-- GPU Finder API: sign-in hardening
-- Run this in the Supabase SQL Editor after users.sql. It is safe to run twice.
--
-- Adds: email verification, server-side sign-out (token_version), account
-- lockout after repeated wrong passwords, one-time email links (verify and
-- password reset), and a shared rate limiter that works on serverless hosts.

-- ---------- users: new columns ----------

-- Accounts that already exist count as verified (the column starts as true),
-- then the default switches to false so every new account must verify.
alter table public.users
    add column if not exists email_verified boolean not null default true;
alter table public.users
    alter column email_verified set default false;

alter table public.users
    -- Raising this number signs the account out everywhere: every token
    -- carries the number it was issued with, and old numbers are refused.
    add column if not exists token_version integer not null default 0
        check (token_version >= 0),
    add column if not exists failed_logins integer not null default 0
        check (failed_logins >= 0),
    add column if not exists locked_until timestamptz;

-- The backend may now change these columns (and only these).
grant update (password_hash, email_verified, token_version, failed_logins, locked_until)
    on table public.users to service_role;


-- ---------- one-time email links ----------

create table if not exists public.auth_tokens (
    id bigint generated always as identity primary key,
    user_id bigint not null references public.users (id) on delete cascade,
    purpose text not null check (purpose in ('verify', 'reset')),
    -- Only a SHA-256 hash of the link's secret is stored, never the secret.
    token_hash text not null unique check (char_length(token_hash) = 64),
    expires_at timestamptz not null,
    used_at timestamptz,
    created_at timestamptz not null default now()
);

create index if not exists auth_tokens_user_purpose_idx
    on public.auth_tokens (user_id, purpose);

alter table public.auth_tokens enable row level security;
revoke all on table public.auth_tokens from anon, authenticated, service_role;
grant select, insert, update on table public.auth_tokens to service_role;


-- ---------- rate limiter ----------
-- Counts hits per key in fixed time windows. Stored in the database so every
-- Vercel instance shares the same counters.

create table if not exists public.rate_limits (
    key text not null check (char_length(key) between 1 and 300),
    window_start timestamptz not null,
    count integer not null default 0,
    primary key (key, window_start)
);

alter table public.rate_limits enable row level security;
revoke all on table public.rate_limits from anon, authenticated, service_role;

-- Returns true if this hit is allowed, false if the key is over its limit.
create or replace function public.hit_rate_limit(
    p_key text,
    p_window_seconds integer,
    p_limit integer
) returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
    v_window timestamptz :=
        to_timestamp(floor(extract(epoch from now()) / p_window_seconds) * p_window_seconds);
    v_count integer;
begin
    insert into public.rate_limits as r (key, window_start, count)
    values (p_key, v_window, 1)
    on conflict (key, window_start) do update set count = r.count + 1
    returning r.count into v_count;

    -- Occasionally clear out old windows so the table stays small.
    if random() < 0.01 then
        delete from public.rate_limits where window_start < now() - interval '2 days';
    end if;

    return v_count <= p_limit;
end;
$$;

revoke execute on function public.hit_rate_limit(text, integer, integer) from public, anon, authenticated;
grant execute on function public.hit_rate_limit(text, integer, integer) to service_role;
