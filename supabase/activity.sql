-- GPU Finder API: recently viewed GPUs, saved comparisons, admin activity log
-- Run this in the Supabase SQL Editor after favorites.sql. It is safe to run twice.
-- Like every other table, browsers cannot reach these directly; only the API can.


-- ---------- recently viewed ----------
-- One row per account and GPU; viewing again just moves it to the top.
-- The API keeps only the newest 20 per account.

create table if not exists public.recently_viewed (
    user_id bigint not null references public.users (id) on delete cascade,
    gpu_id bigint not null references public.gpus (id) on delete cascade,
    viewed_at timestamptz not null default now(),
    primary key (user_id, gpu_id)
);

create index if not exists recently_viewed_user_time_idx
    on public.recently_viewed (user_id, viewed_at desc);

alter table public.recently_viewed enable row level security;
revoke all on table public.recently_viewed from anon, authenticated, service_role;
grant select, insert, delete on table public.recently_viewed to service_role;
grant update (viewed_at) on table public.recently_viewed to service_role;


-- ---------- saved comparisons ----------

create table if not exists public.saved_comparisons (
    id bigint generated always as identity primary key,
    user_id bigint not null references public.users (id) on delete cascade,
    gpu_a_id bigint not null references public.gpus (id) on delete cascade,
    gpu_b_id bigint not null references public.gpus (id) on delete cascade,
    name text check (name is null or char_length(name) between 1 and 80),
    created_at timestamptz not null default now(),
    check (gpu_a_id <> gpu_b_id),
    -- The same pair can only be saved once per account.
    unique (user_id, gpu_a_id, gpu_b_id)
);

create index if not exists saved_comparisons_user_idx
    on public.saved_comparisons (user_id, created_at desc);

alter table public.saved_comparisons enable row level security;
revoke all on table public.saved_comparisons from anon, authenticated, service_role;
grant select, insert, delete on table public.saved_comparisons to service_role;


-- ---------- admin activity log ----------
-- Append-only: the API can add and read entries but never change or delete
-- them, so the history can't be rewritten through the API.

create table if not exists public.audit_log (
    id bigint generated always as identity primary key,
    admin_id bigint references public.users (id) on delete set null,
    admin_email text not null check (char_length(admin_email) <= 254),
    action text not null
        check (action in ('gpu.create', 'gpu.update', 'gpu.delete', 'image.upload', 'image.remove')),
    -- No foreign key: entries must survive the GPU being deleted.
    gpu_id bigint,
    gpu_model text check (gpu_model is null or char_length(gpu_model) <= 120),
    -- For updates: {"field": [old, new], ...}
    changes jsonb,
    created_at timestamptz not null default now()
);

create index if not exists audit_log_created_idx on public.audit_log (created_at desc);

alter table public.audit_log enable row level security;
revoke all on table public.audit_log from anon, authenticated, service_role;
grant select, insert on table public.audit_log to service_role;
