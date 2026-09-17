-- Skill Factory V1.0 foundation. Apply through a Supabase database admin session.
-- Tables remain inaccessible to browser roles; FastAPI uses the server-only key.

create extension if not exists pgcrypto;

create table public.skills (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  name text not null check (char_length(name) between 1 and 160),
  description text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  archived_at timestamptz
);

create table public.skill_versions (
  id uuid primary key default gen_random_uuid(),
  skill_id uuid not null references public.skills(id) on delete restrict,
  version text not null check (version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),
  layer_type text not null default 'compiled' check (layer_type in ('core', 'domain', 'personal', 'compiled')),
  status text not null default 'draft' check (status in ('draft', 'candidate', 'evaluating', 'passed', 'failed', 'archived')),
  artifact_storage_path text not null unique,
  artifact_hash text not null check (artifact_hash ~ '^[a-f0-9]{64}$'),
  created_by_engine text not null default 'import',
  created_from_job_id uuid,
  created_at timestamptz not null default now(),
  promoted_at timestamptz,
  unique (skill_id, version)
);

create table public.skill_lineage (
  id uuid primary key default gen_random_uuid(),
  parent_version_id uuid not null references public.skill_versions(id) on delete restrict,
  child_version_id uuid not null references public.skill_versions(id) on delete restrict,
  relation text not null check (relation in ('distilled_from', 'fused_from', 'personalized_from', 'evolved_from', 'refreshed_from', 'derived_from')),
  created_at timestamptz not null default now(),
  check (parent_version_id <> child_version_id),
  unique (parent_version_id, child_version_id, relation)
);

create table public.sources (
  id uuid primary key default gen_random_uuid(),
  source_type text not null check (source_type in ('github_repo', 'web_source', 'document', 'manual', 'demonstration', 'production_trace', 'existing_skill')),
  uri text not null,
  repo_ref text,
  content_hash text,
  license text,
  metadata jsonb not null default '{}'::jsonb,
  captured_at timestamptz not null default now()
);

create table public.skill_version_sources (
  skill_version_id uuid not null references public.skill_versions(id) on delete cascade,
  source_id uuid not null references public.sources(id) on delete restrict,
  role text not null check (role in ('primary', 'supporting', 'example', 'contradicting')),
  evidence_grade text check (evidence_grade in ('A', 'B', 'C', 'D')),
  primary key (skill_version_id, source_id, role)
);

create table public.evidence_items (
  id uuid primary key default gen_random_uuid(),
  skill_id uuid references public.skills(id) on delete cascade,
  evidence_type text not null check (evidence_type in ('demonstration', 'correction', 'choice', 'good_example', 'bad_example', 'preference', 'decision_rationale')),
  title text not null,
  content jsonb not null,
  rationale text,
  rating smallint check (rating between 1 and 5),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  archived_at timestamptz
);

create table public.eval_datasets (
  id uuid primary key default gen_random_uuid(),
  skill_id uuid references public.skills(id) on delete set null,
  name text not null,
  dataset_type text not null check (dataset_type in ('functional', 'personal', 'regression', 'generalization', 'trigger')),
  version integer not null default 1 check (version > 0),
  split text not null check (split in ('dev', 'holdout')),
  parent_dataset_id uuid references public.eval_datasets(id) on delete restrict,
  is_locked boolean not null default false,
  created_at timestamptz not null default now(),
  unique nulls not distinct (skill_id, name, version)
);

create table public.eval_cases (
  id uuid primary key default gen_random_uuid(),
  dataset_id uuid not null references public.eval_datasets(id) on delete restrict,
  prompt text not null,
  expected_output text,
  expectations jsonb not null default '{}'::jsonb,
  files jsonb not null default '[]'::jsonb,
  tags jsonb not null default '[]'::jsonb,
  source_evidence_id uuid references public.evidence_items(id) on delete set null,
  created_at timestamptz not null default now()
);

create table public.eval_runs (
  id uuid primary key default gen_random_uuid(),
  skill_version_id uuid not null references public.skill_versions(id) on delete restrict,
  baseline_version_id uuid references public.skill_versions(id) on delete restrict,
  dataset_id uuid not null references public.eval_datasets(id) on delete restrict,
  engine text not null,
  model text,
  grader_metadata jsonb not null default '{}'::jsonb,
  status text not null default 'queued' check (status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
  summary jsonb not null default '{}'::jsonb,
  started_at timestamptz,
  finished_at timestamptz
);

create table public.eval_case_results (
  id uuid primary key default gen_random_uuid(),
  eval_run_id uuid not null references public.eval_runs(id) on delete cascade,
  eval_case_id uuid not null references public.eval_cases(id) on delete restrict,
  passed boolean,
  score numeric,
  grader_output jsonb not null default '{}'::jsonb,
  candidate_output_path text,
  baseline_output_path text,
  latency_ms integer check (latency_ms >= 0),
  cost numeric check (cost >= 0),
  unique (eval_run_id, eval_case_id)
);

create table public.releases (
  id uuid primary key default gen_random_uuid(),
  skill_id uuid not null references public.skills(id) on delete restrict,
  skill_version_id uuid not null references public.skill_versions(id) on delete restrict,
  environment text not null default 'production' check (environment in ('production', 'shadow', 'canary')),
  release_state text not null check (release_state in ('active', 'superseded', 'rolled_back')),
  reason text,
  manual_override boolean not null default false,
  override_reason text,
  released_at timestamptz not null default now(),
  superseded_at timestamptz,
  rollback_from_release_id uuid references public.releases(id) on delete restrict,
  check ((manual_override and override_reason is not null) or not manual_override)
);
create unique index one_active_release_per_environment
  on public.releases (skill_id, environment) where superseded_at is null;

create table public.executions (
  id uuid primary key default gen_random_uuid(),
  skill_version_id uuid not null references public.skill_versions(id) on delete restrict,
  external_trace_id text,
  input_summary text not null,
  output_summary text,
  status text not null check (status in ('running', 'succeeded', 'failed', 'cancelled')),
  user_rating smallint check (user_rating between 1 and 5),
  feedback text,
  created_at timestamptz not null default now()
);

create table public.audit_events (
  id uuid primary key default gen_random_uuid(),
  aggregate_type text not null,
  aggregate_id uuid not null,
  event_type text not null,
  actor text not null default 'local-operator',
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- Private bucket for normalized, immutable packages. The service role is the only
-- actor used by the V1 API; no browser policy is created.
insert into storage.buckets (id, name, public)
values ('skill-artifacts', 'skill-artifacts', false)
on conflict (id) do nothing;

create function public.prevent_skill_version_artifact_mutation()
returns trigger
language plpgsql
as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'skill versions are immutable';
  end if;
  if old.skill_id is distinct from new.skill_id
    or old.version is distinct from new.version
    or old.artifact_storage_path is distinct from new.artifact_storage_path
    or old.artifact_hash is distinct from new.artifact_hash
    or old.layer_type is distinct from new.layer_type
    or old.created_by_engine is distinct from new.created_by_engine
    or old.created_from_job_id is distinct from new.created_from_job_id then
    raise exception 'skill version artifact identity is immutable';
  end if;
  return new;
end;
$$;
revoke all on function public.prevent_skill_version_artifact_mutation() from public;
create trigger skill_versions_immutable_artifact
before update or delete on public.skill_versions
for each row execute function public.prevent_skill_version_artifact_mutation();

-- API hardening: no browser role can access factory metadata directly.
revoke all on all tables in schema public from anon, authenticated;
grant usage on schema public to service_role;
grant select, insert, update, delete on all tables in schema public to service_role;
alter default privileges in schema public revoke all on tables from anon, authenticated;
alter default privileges in schema public grant select, insert, update, delete on tables to service_role;

alter table public.skills enable row level security;
alter table public.skill_versions enable row level security;
alter table public.skill_lineage enable row level security;
alter table public.sources enable row level security;
alter table public.skill_version_sources enable row level security;
alter table public.evidence_items enable row level security;
alter table public.eval_datasets enable row level security;
alter table public.eval_cases enable row level security;
alter table public.eval_runs enable row level security;
alter table public.eval_case_results enable row level security;
alter table public.releases enable row level security;
alter table public.executions enable row level security;
alter table public.audit_events enable row level security;
