# Skill Factory

Local-first control plane for versioned, evidence-backed Agent Skills.

## Current vertical slices

The first vertical slice supports safe package import, immutable artifact registration,
version listing, promotion, rollback, and export. It deliberately keeps the browser
away from server credentials: the Next.js app talks only to FastAPI, and FastAPI talks
to Supabase using a server-only secret key.

V1.1 adds a durable local job queue with fixture, AREX/Disco, and SkillAlchemy
adapters. V1.2 adds typed personal evidence, versioned dev/holdout datasets, immutable
datasets once evaluated, deterministic fixture evaluation, and persisted release-gate
decisions. A non-passed version still needs a manual override with an audit reason.

V1.3 adds `POST /jobs/personalize`: it creates an unpromoted candidate from a chosen
baseline, selected evidence, and explicitly selected **dev** datasets. The worker
extracts the immutable baseline package into its isolated workspace, registers the
candidate as a new immutable version, and records `personalized_from` lineage.

## Prerequisites

- Node.js 22+ and pnpm 11+
- Python 3.14+ and uv
- A Supabase project with the migration in `migrations/0001_skill_factory.sql` applied
- A private Storage bucket named `skill-artifacts`

## Setup

```bash
cp .env.example .env
uv sync --all-groups
pnpm install
uv run python scripts/apply_migration.py migrations/0001_skill_factory.sql
uv run python scripts/apply_migration.py migrations/0002_atomic_releases_and_jobs.sql
uv run python scripts/apply_migration.py migrations/0003_job_claiming.sql
uv run python scripts/apply_migration.py migrations/0004_evidence_eval_integrity.sql
uv run python scripts/apply_migration.py migrations/0005_eval_trigger_return_fix.sql
uv run uvicorn apps.api.app.main:app --reload --port 8000
pnpm dev:web
```

In a second terminal, run the local worker. It uses deterministic fixture mode by
default and only invokes a configured external engine when a job explicitly selects it.

```bash
uv run python -m workers.main --poll
```

The API derives the project URL from `SPB_PROJECT_ID`. `SPB_SECRET_KEY` must remain
server-side; do not add it to a `NEXT_PUBLIC_` variable. `SPB_ACCESS_TOKEN` is only
used by the migration script and should have Supabase `database_write` permission.

## Tests

```bash
uv run pytest
```

Tests use in-memory fixtures and do not call Supabase or a model provider.

## Evaluation contract

Create all cases before calling `POST /eval-runs`. Running an evaluation locks its
dataset permanently; changes require a new dataset version. Release gates require a
functional holdout score of at least 0.8, require a personal holdout when one exists,
and reject any baseline regression. The fixture evaluator only consumes explicit
`fixture_candidate_pass` / `fixture_baseline_pass` case assertions. It is a test
harness, not a claim that an external model was evaluated.

Future optimization workers must obtain examples through the `get_dev_eval_cases`
database function, which never returns holdout cases.

## Candidate personalization

`POST /jobs/personalize` accepts `baseline_version_id`, one or more `evidence_ids`,
and optional `dev_dataset_ids`. The API rejects evidence or datasets belonging to a
different Skill and rejects every non-dev dataset before the job is queued. The
candidate still needs holdout evaluation and a passing gate before normal production
promotion.
