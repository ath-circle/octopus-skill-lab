-- A single local worker claims a job atomically. The lease makes a crashed worker
-- recoverable without a separate queue service.

create function public.claim_next_skill_job(p_lease_seconds integer default 300)
returns public.jobs
language plpgsql
security invoker
set search_path = public
as $$
declare
  claimed public.jobs;
begin
  if p_lease_seconds < 30 or p_lease_seconds > 3600 then
    raise exception 'lease must be between 30 and 3600 seconds' using errcode = '22023';
  end if;
  select * into claimed
  from public.jobs
  where status = 'queued'
     or (status = 'running' and lease_expires_at < now())
  order by created_at
  for update skip locked
  limit 1;
  if not found then
    return null;
  end if;
  update public.jobs
  set status = 'running',
      attempt_count = claimed.attempt_count + 1,
      started_at = coalesce(claimed.started_at, now()),
      lease_expires_at = now() + make_interval(secs => p_lease_seconds),
      error = null
  where id = claimed.id
  returning * into claimed;
  return claimed;
end;
$$;

create function public.finish_skill_job(
  p_job_id uuid,
  p_status text,
  p_output jsonb default null,
  p_error text default null
)
returns public.jobs
language plpgsql
security invoker
set search_path = public
as $$
declare
  completed public.jobs;
begin
  if p_status not in ('succeeded', 'failed', 'cancelled') then
    raise exception 'invalid terminal status' using errcode = '22023';
  end if;
  update public.jobs
  set status = p_status,
      output = p_output,
      error = p_error,
      finished_at = now(),
      lease_expires_at = null
  where id = p_job_id and status = 'running'
  returning * into completed;
  if not found then
    raise exception 'job cannot be completed from its current state' using errcode = '22023';
  end if;
  insert into public.audit_events (aggregate_type, aggregate_id, event_type, payload)
  values ('job', completed.id, 'job.' || p_status, jsonb_build_object('engine', completed.engine));
  return completed;
end;
$$;

revoke all on function public.claim_next_skill_job(integer) from public;
revoke all on function public.finish_skill_job(uuid, text, jsonb, text) from public;
grant execute on function public.claim_next_skill_job(integer) to service_role;
grant execute on function public.finish_skill_job(uuid, text, jsonb, text) to service_role;
