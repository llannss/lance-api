-- GPU Finder API: GPU pictures in Supabase Storage
-- Run this in the Supabase SQL Editor after auth_upgrade.sql. It is safe to run twice.
--
-- Pictures live in a public bucket so the website can show them straight
-- from Supabase's CDN. Only the API (service role) can add or remove them:
-- there are no storage policies for anon or authenticated, so browsers
-- cannot upload, overwrite or delete anything.

-- ---------- gpus: picture address ----------

alter table public.gpus
    add column if not exists image_url text
        check (image_url is null or (char_length(image_url) <= 500 and image_url like 'https://%'));


-- ---------- bucket ----------

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'gpu-images',
    'gpu-images',
    true,                    -- anyone may view a picture by its URL
    2097152,                 -- 2 MB per file (the API stores ~50-150 KB WebP)
    array['image/webp']      -- the API converts every upload to WebP
)
on conflict (id) do update
    set public = excluded.public,
        file_size_limit = excluded.file_size_limit,
        allowed_mime_types = excluded.allowed_mime_types;
