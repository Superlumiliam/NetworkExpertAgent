create extension if not exists vector with schema extensions;
create extension if not exists pgcrypto;

create table if not exists public.rfc_knowledge_base (
  id uuid primary key default gen_random_uuid(),
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  embedding extensions.vector not null,
  rfc_id text generated always as (metadata->>'rfc_id') stored,
  content_hash text not null,
  created_at timestamptz not null default now(),
  unique (rfc_id, content_hash)
);

create index if not exists rfc_knowledge_base_rfc_id_idx
  on public.rfc_knowledge_base (rfc_id);

create index if not exists rfc_knowledge_base_embedding_hnsw_idx
  on public.rfc_knowledge_base
  using hnsw (embedding extensions.vector_cosine_ops);

alter table public.rfc_knowledge_base enable row level security;
