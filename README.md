# Skill Factory

Local-first control plane for versioned, evidence-backed Agent Skills.

## Current vertical slices

The first vertical slice supports safe package import, immutable artifact registration,
version listing, promotion, rollback, and export. It deliberately keeps the browser
away from server credentials: the Next.js app talks only to FastAPI, and FastAPI talks
to Supabase using a server-only secret key.

V1.1 adds a durable local job queue with fixture, AREX/Disco, and SkillAlchemy
adapters. V1.2 adds typed personal evidence, versioned dev/holdout datasets, immutable
datasets once evaluated, isolated baseline/candidate Codex evaluation, and persisted
release-gate decisions. A non-passed version still needs a manual override with an audit reason.

V1.3 adds `POST /jobs/personalize`: it creates an unpromoted candidate from a chosen
baseline, selected evidence, and explicitly selected **dev** datasets. The worker
extracts the immutable baseline package into its isolated workspace, registers the
candidate as a new immutable version, and records `personalized_from` lineage.

V1.4 adds `POST /jobs/fuse`, creating a new Skill from two or more immutable source
versions and recording `fused_from` lineage for every source. Personalization now has
an explicit `skillcreator` adapter for the upstream Anthropic Skill Creator package;
it remains unavailable until its local package directory is deliberately configured.

V1.5 completes the local runtime loop: external engine packages are copied into each
job workspace before invocation, every engine subprocess has a bounded timeout, and a
stopped worker records its claimed job as failed rather than leaving it running. The
benchmark path is intentionally separate from those authoring engines: local Codex
executes baseline and candidate independently, then a new blind Codex invocation
grades anonymous outputs. A passing gate makes a candidate eligible for promotion; it
does not promote it automatically.

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

Tests use in-memory fakes and do not call Supabase or a model provider.

## Evaluation contract

Create all cases before calling `POST /eval-runs`. Running an evaluation locks its
dataset permanently; changes require a new dataset version. Release gates require a
functional holdout pass rate of at least 0.8, require a personal holdout when one exists,
and reject any baseline regression. Evaluation requires a baseline and the `codex`
engine; it never falls back to fixture assertions. Each case runs candidate and baseline
Skills in separate ephemeral Codex workspaces. Deterministic checks run first. When they
do not decide the case, a third ephemeral Codex grader sees only the task, rubric, and
randomized anonymous outputs A/B. Executor and grader transcripts are persisted only
after every isolated role completes.

Cases may define `expectations.rubric` and `expectations.deterministic_checks`. Supported
deterministic check types are `contains`, `not_contains`, `equals`, `regex`, `valid_json`,
`min_length`, and `max_length`. A model-graded case must provide a rubric or
`expected_output`; missing grading inputs fail the run closed.

Phoenix is a local optional service, not the registry: start it with
`PHOENIX_HOST=127.0.0.1 PHOENIX_PORT=6006 uv run phoenix serve`. `POST /executions`
creates an OTLP trace and records its trace ID beside the exact immutable Skill version;
`POST /executions/{id}/feedback` stores operator feedback. Promptfoo is represented by
an optional adapter (`PROMPTFOO_ENABLED=false` by default) for repeatable regression
suites, but it never silently replaces the blind Codex gate.

External engines are deliberately installed outside the repository in `.tools/`.
Point `SKILLALCHEMY_SKILL_PATH` at `.tools/skillalchemy` and
`SKILLCREATOR_SKILL_PATH` at `.tools/anthropic-skills/skills/skill-creator` after
installing those upstream packages. Install DisCo separately as `@arex-skill/disco`
and set `AREX_DISCO_BIN` to its executable. Health checks stay unavailable until both
the executable and the matching upstream package are configured; this is intentional
fail-closed behavior.

Future optimization workers must obtain examples through the `get_dev_eval_cases`
database function, which never returns holdout cases.

## Local V1 runtime checklist

Run authoring jobs with `SKILL_FACTORY_ENGINE_MODE=live`; fixture mode is reserved for
automated tests. Each live adapter fails closed when its executable or staged upstream
package is missing. `ENGINE_TIMEOUT_SECONDS` bounds authoring jobs and
`CODEX_BENCHMARK_TIMEOUT_SECONDS` separately bounds every executor/grader role.

AREX uses the standalone DisCo executable and therefore requires its own provider
authentication (for example, `disco` followed by `/login`); it does not inherit the
Codex desktop login. Do not substitute a fixture result if that authentication is not
available.

## Candidate personalization

`POST /jobs/personalize` accepts `baseline_version_id`, one or more `evidence_ids`,
and optional `dev_dataset_ids`. The API rejects evidence or datasets belonging to a
different Skill and rejects every non-dev dataset before the job is queued. The
candidate still needs holdout evaluation and a passing gate before normal production
promotion.
