-- GPU Finder API: favorite GPUs saved to each account
-- Run this in the Supabase SQL Editor after storage.sql. It is safe to run twice.

create table if not exists public.favorites (
    user_id bigint not null references public.users (id) on delete cascade,
    gpu_id bigint not null references public.gpus (id) on delete cascade,
    created_at timestamptz not null default now(),
    -- One row per account and GPU: hearting twice changes nothing.
    primary key (user_id, gpu_id)
);

-- Newest favorites first for one account.
create index if not exists favorites_user_created_idx
    on public.favorites (user_id, created_at desc);

-- Browsers cannot read or change favorites directly; only the API can,
-- and it always uses the signed-in account's ID from the login token.
alter table public.favorites enable row level security;
revoke all on table public.favorites from anon, authenticated, service_role;
grant select, insert, delete on table public.favorites to service_role;
