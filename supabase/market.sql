-- GPU Nexus Marketplace: used-GPU listings, their photos, and messages
-- between buyers and sellers.
-- Run this in the Supabase SQL Editor after activity.sql. It is safe to run twice.
-- Like every other table, browsers cannot reach these directly; only the API
-- can, and it always takes the account from the login token.


-- ---------- listings ----------

create table if not exists public.listings (
    id bigint generated always as identity primary key,
    seller_id bigint not null references public.users (id) on delete cascade,
    -- The catalog GPU this is, if the seller linked one. A GPU removed from
    -- the catalog leaves its listings in place, just unlinked.
    gpu_id bigint references public.gpus (id) on delete set null,
    title text not null check (char_length(title) between 3 and 120),
    description text not null default '' check (char_length(description) <= 2000),
    condition text not null
        check (condition in ('new', 'like_new', 'good', 'fair', 'for_parts')),
    price numeric(12, 2) not null check (price > 0 and price < 100000000),
    -- Sellers price in pesos or dollars; buyers can view either.
    currency text not null default 'PHP' check (currency in ('PHP', 'USD')),
    location text not null default '' check (char_length(location) <= 80),
    -- Public URLs of up to six WebP photos in the listing-photos bucket.
    -- The first one is the cover.
    photos jsonb not null default '[]'::jsonb
        check (jsonb_typeof(photos) = 'array' and jsonb_array_length(photos) <= 6),
    status text not null default 'active' check (status in ('active', 'sold')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists listings_status_created_idx on public.listings (status, created_at desc);
create index if not exists listings_gpu_idx on public.listings (gpu_id, status);
create index if not exists listings_seller_idx on public.listings (seller_id, created_at desc);

alter table public.listings enable row level security;
revoke all on table public.listings from anon, authenticated, service_role;
grant select, insert, update, delete on table public.listings to service_role;


-- ---------- conversations: one per listing and buyer ----------

create table if not exists public.conversations (
    id bigint generated always as identity primary key,
    listing_id bigint not null references public.listings (id) on delete cascade,
    buyer_id bigint not null references public.users (id) on delete cascade,
    seller_id bigint not null references public.users (id) on delete cascade,
    created_at timestamptz not null default now(),
    -- The newest message, kept here so the inbox is one query.
    last_message_at timestamptz not null default now(),
    last_sender_id bigint,
    last_body text not null default '' check (char_length(last_body) <= 2000),
    -- When each side last opened the conversation (for "new" marks).
    buyer_read_at timestamptz,
    seller_read_at timestamptz,
    check (buyer_id <> seller_id),
    unique (listing_id, buyer_id)
);

create index if not exists conversations_buyer_idx on public.conversations (buyer_id, last_message_at desc);
create index if not exists conversations_seller_idx on public.conversations (seller_id, last_message_at desc);

alter table public.conversations enable row level security;
revoke all on table public.conversations from anon, authenticated, service_role;
grant select, insert, update, delete on table public.conversations to service_role;


-- ---------- messages ----------

create table if not exists public.messages (
    id bigint generated always as identity primary key,
    conversation_id bigint not null references public.conversations (id) on delete cascade,
    sender_id bigint not null references public.users (id) on delete cascade,
    body text not null check (char_length(body) between 1 and 2000),
    created_at timestamptz not null default now()
);

create index if not exists messages_conversation_idx on public.messages (conversation_id, created_at);

alter table public.messages enable row level security;
revoke all on table public.messages from anon, authenticated, service_role;
grant select, insert on table public.messages to service_role;


-- ---------- photo bucket ----------
-- Public, so the Marketplace shows photos straight from Supabase's CDN. Only
-- the API (service role) can add or remove files: browsers can't upload,
-- overwrite or delete anything here.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'listing-photos',
    'listing-photos',
    true,
    2097152,                 -- 2 MB per file (the API stores ~100-300 KB WebP)
    array['image/webp']      -- the API converts every upload to WebP
)
on conflict (id) do update
    set public = excluded.public,
        file_size_limit = excluded.file_size_limit,
        allowed_mime_types = excluded.allowed_mime_types;
