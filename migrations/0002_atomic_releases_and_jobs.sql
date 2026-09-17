-- Keep a production pointer transition atomic. These functions run as invoker;
-- only the server-side service_role is granted execution.

create table public.jobs (
  id uuid primary key default gen_random_uuid(),
  job_type text not null,
  engine text not null,
  status text not null default 'queued' check (status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
  input jsonb not null default '{}'::jsonb,
  output jsonb,
  workspace_path text,
  idempotency_key text unique,
  attempt_count integer not null default 0 check (attempt_count >= 0),
  lease_expires_at timestamptz,
  started_at timestamptz,
  finished_at timestamptz,
  error text,
  created_at timestamptz not null default now()
);

create function public.promote_skill_version(
  p_skill_version_id uuid,
  p_reason text default null,
  p_manual_override boolean default false,
  p_override_reason text default null
)
returns public.releases
language plpgsql
security invoker
set search_path = public
as $$
declare
  target public.skill_versions;
  created_release public.releases;
begin
  select * into target from public.skill_versions where id = p_skill_version_id for update;
  if not found then
    raise exception 'skill version was not found' using errcode = 'P0002';
  end if;
  perform 1 from public.skills where id = target.skill_id for update;
  if target.status <> 'passed' and not p_manual_override then
    raise exception 'a non-passed version requires a manual override' using errcode = '22023';
  end if;
  if p_manual_override and coalesce(trim(p_override_reason), '') = '' then
    raise exception 'a manual override requires a reason' using errcode = '22023';
  end if;

  update public.releases
  set release_state = 'superseded', superseded_at = now()
  where skill_id = target.skill_id and environment = 'production' and superseded_at is null;

  insert into public.releases (
    skill_id, skill_version_id, environment, release_state, reason, manual_override, override_reason
  ) values (
    target.skill_id, target.id, 'production', 'active', p_reason, p_manual_override, p_override_reason
  ) returning * into created_release;

  update public.skill_versions set promoted_at = coalesce(promoted_at, now()) where id = target.id;
  insert into public.audit_events (aggregate_type, aggregate_id, event_type, payload)
  values ('release', created_release.id, 'release.promoted', jsonb_build_object(
    'version_id', target.id, 'manual_override', p_manual_override
  ));
  return created_release;
end;
$$;

create function public.rollback_skill_release(
  p_skill_id uuid,
  p_target_release_id uuid,
  p_reason text
)
returns public.releases
language plpgsql
security invoker
set search_path = public
as $$
declare
  target public.releases;
  created_release public.releases;
begin
  if coalesce(trim(p_reason), '') = '' then
    raise exception 'a rollback requires a reason' using errcode = '22023';
  end if;
  perform 1 from public.skills where id = p_skill_id for update;
  if not found then
    raise exception 'skill was not found' using errcode = 'P0002';
  end if;
  select * into target from public.releases
  where id = p_target_release_id and skill_id = p_skill_id
  for key share;
  if not found then
    raise exception 'target release does not belong to skill' using errcode = '22023';
  end if;

  update public.releases
  set release_state = 'superseded', superseded_at = now()
  where skill_id = p_skill_id and environment = 'production' and superseded_at is null;

  insert into public.releases (
    skill_id, skill_version_id, environment, release_state, reason, rollback_from_release_id
  ) values (
    p_skill_id, target.skill_version_id, 'production', 'active', p_reason, target.id
  ) returning * into created_release;

  insert into public.audit_events (aggregate_type, aggregate_id, event_type, payload)
  values ('release', created_release.id, 'release.rolled_back', jsonb_build_object(
    'target_release_id', target.id, 'reason', p_reason
  ));
  return created_release;
end;
$$;

revoke all on function public.promote_skill_version(uuid, text, boolean, text) from public;
revoke all on function public.rollback_skill_release(uuid, uuid, text) from public;
grant execute on function public.promote_skill_version(uuid, text, boolean, text) to service_role;
grant execute on function public.rollback_skill_release(uuid, uuid, text) to service_role;

grant select, insert, update, delete on public.jobs to service_role;
alter table public.jobs enable row level security;
