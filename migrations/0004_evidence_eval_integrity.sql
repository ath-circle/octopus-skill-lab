-- V1.2: keep evaluation inputs immutable once locked and record gate decisions.
-- Browser roles remain blocked; this is operated through the server-side API only.

create table public.eval_gate_decisions (
  id uuid primary key default gen_random_uuid(),
  skill_version_id uuid not null references public.skill_versions(id) on delete restrict,
  decision text not null check (decision in ('passed', 'failed', 'incomplete')),
  policy jsonb not null,
  summary jsonb not null,
  created_at timestamptz not null default now()
);
create index eval_gate_decisions_version_created_idx
  on public.eval_gate_decisions (skill_version_id, created_at desc);

create function public.prevent_locked_eval_dataset_mutation()
returns trigger
language plpgsql
as $$
begin
  if old.is_locked then
    raise exception 'locked evaluation datasets are immutable';
  end if;
  if old.split = 'holdout' and new.split = 'dev' then
    raise exception 'a holdout dataset cannot be downgraded to dev';
  end if;
  return new;
end;
$$;
revoke all on function public.prevent_locked_eval_dataset_mutation() from public;
create trigger eval_datasets_locked_immutable
before update or delete on public.eval_datasets
for each row execute function public.prevent_locked_eval_dataset_mutation();

create function public.prevent_locked_eval_case_mutation()
returns trigger
language plpgsql
as $$
declare
  target_dataset_id uuid := coalesce(old.dataset_id, new.dataset_id);
begin
  if exists (select 1 from public.eval_datasets where id = target_dataset_id and is_locked) then
    raise exception 'cases in a locked evaluation dataset are immutable';
  end if;
  return coalesce(new, old);
end;
$$;
revoke all on function public.prevent_locked_eval_case_mutation() from public;
create trigger eval_cases_locked_immutable
before update or delete on public.eval_cases
for each row execute function public.prevent_locked_eval_case_mutation();

-- Future optimization workers must use this function rather than reading eval_cases
-- directly. It will never disclose a holdout split.
create function public.get_dev_eval_cases(p_dataset_id uuid)
returns setof public.eval_cases
language sql
security invoker
set search_path = public
as $$
  select c.*
  from public.eval_cases c
  join public.eval_datasets d on d.id = c.dataset_id
  where c.dataset_id = p_dataset_id and d.split = 'dev'
  order by c.created_at;
$$;
revoke all on function public.get_dev_eval_cases(uuid) from public;
grant execute on function public.get_dev_eval_cases(uuid) to service_role;

grant select, insert, update, delete on public.eval_gate_decisions to service_role;
alter table public.eval_gate_decisions enable row level security;
