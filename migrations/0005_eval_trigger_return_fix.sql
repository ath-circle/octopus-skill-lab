-- Ensure immutability triggers preserve normal delete semantics for unlocked drafts.

create or replace function public.prevent_locked_eval_dataset_mutation()
returns trigger
language plpgsql
as $$
begin
  if old.is_locked then
    raise exception 'locked evaluation datasets are immutable';
  end if;
  if tg_op = 'DELETE' then
    return old;
  end if;
  if old.split = 'holdout' and new.split = 'dev' then
    raise exception 'a holdout dataset cannot be downgraded to dev';
  end if;
  return new;
end;
$$;

create or replace function public.prevent_locked_eval_case_mutation()
returns trigger
language plpgsql
as $$
declare
  target_dataset_id uuid := coalesce(old.dataset_id, new.dataset_id);
begin
  if exists (select 1 from public.eval_datasets where id = target_dataset_id and is_locked) then
    raise exception 'cases in a locked evaluation dataset are immutable';
  end if;
  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;
