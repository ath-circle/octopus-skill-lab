# PRD — Skill Factory / OPC SkillOps

> **Version:** 1.0  
> **Date:** 2026-09-17  
> **Product type:** Local-first Skill lifecycle/control plane  
> **Primary user:** Single technical user building and operating reusable Agent Skills  
> **Implementation target:** Codex / Claude Code  
> **Delivery:** V1 first; V2 extends production learning.

---

# 1. Product Summary

Skill Factory is a control plane for turning external knowledge, open-world research, and personal decision evidence into versioned Agent Skills.

It integrates existing open-source engines rather than reimplementing their research algorithms.

The system must support:

```text
Create
→ Distill
→ Fuse
→ Personalize
→ Evaluate
→ Version
→ Promote
→ Export / Use
→ Observe
→ Improve later
```

V1 focuses on deterministic lifecycle management.

V2 adds production trace learning and autonomous candidate generation, but **never autonomous promotion**.

---

# 2. Goals

## 2.1 V1 goals

V1 must allow the user to:

1. create a Skill from a GitHub repository using AREX/DisCo;
2. create a Skill from an underspecified requirement using SkillAlchemy;
3. fuse two or more Skills using SkillAlchemy;
4. import an existing Skill directory;
5. add personal evidence:
   - demonstrations;
   - corrections;
   - choice cases;
   - good/bad examples;
   - rationale;
6. create an improved/personalized candidate using Skill Creator;
7. build and version eval datasets;
8. evaluate candidate vs baseline;
9. store functional/personal/regression/trigger results;
10. promote an approved version to production;
11. roll back manually to an earlier version;
12. export any version as a portable Skill package;
13. capture production/test traces in Phoenix;
14. preserve lineage and provenance.

## 2.2 V2 goals

V2 must additionally:

1. ingest production trace outcomes/feedback;
2. classify root cause and learnability;
3. create curated trace sets;
4. run a genericized Trace2Skill evolution engine;
5. produce candidate updates with explicit proposed changes;
6. run dev + held-out + regression + generalization eval gates;
7. support automated upstream repository refresh;
8. re-compose/refuse Skills while preserving the personal layer;
9. add shadow/canary states;
10. support automated rollback recommendation;
11. support richer cost/latency tracking;
12. support reusable personal profiles across compatible Skills.

---

# 3. Users and Use Cases

## 3.1 Primary user

A technical operator building a personal multi-agent workbench / OPC.

The user is comfortable with:

- GitHub;
- API keys;
- Codex / Claude Code;
- local servers;
- Supabase;
- CLI tools.

V1 does not need onboarding for non-technical end users.

## 3.2 Core use cases

### UC-01 — Repo to Skill

```text
User enters GitHub repo
→ system starts AREX/DisCo job
→ receives generated Skill package
→ normalizes package
→ registers v0.1.0
→ stores source URL / commit / license metadata
```

### UC-02 — Requirement to Skill

```text
User describes unique capability
→ system starts SkillAlchemy
→ research + implicit requirements + procedures
→ output normalized Skill
→ register draft version
```

### UC-03 — Fuse Skills

```text
User selects Skill A + Skill B
→ enters fusion objective
→ SkillAlchemy fusion
→ new Skill C
→ lineage:
   C fused_from A
   C fused_from B
```

### UC-04 — Personalize Skill

```text
User selects general Skill
→ adds examples / corrections / decisions
→ selects development cases
→ Skill Creator Improve
→ candidate personalized Skill
→ evaluate against baseline
```

### UC-05 — Promote Skill

```text
candidate
→ eval gate
→ PASS
→ user approves
→ immutable release
→ production pointer updated
```

### UC-06 — Export Skill

Export selected version as `.zip` containing the portable Skill directory and factory metadata.

### UC-07 — Production learning (V2)

```text
production trace
→ outcome + feedback
→ curator
→ learnable trace set
→ Trace2Skill
→ candidate
→ eval gate
→ optional promote
```

---

# 4. System Architecture

```text
┌──────────────────────────────────────────────┐
│                  WEB UI                      │
│ Next.js                                      │
└───────────────────┬──────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│              CONTROL API                     │
│ FastAPI                                      │
│                                              │
│ Registry / Jobs / Lineage / Provenance       │
│ Personal Evidence / Eval / Release           │
└───────────────────┬──────────────────────────┘
                    │
        ┌───────────┼────────────┐
        │           │            │
        ▼           ▼            ▼
  Supabase DB   Supabase      Phoenix
                Storage       Observability
                    │
                    ▼
┌──────────────────────────────────────────────┐
│                  WORKER                      │
│ isolated per-job workspace                   │
└───────┬────────────┬────────────┬─────────────┘
        │            │            │
        ▼            ▼            ▼
      AREX      SkillAlchemy   Skill Creator
        │            │            │
        └────────────┴──────┬─────┘
                            ▼
                      Normalizer
                            ▼
                    Canonical Skill
```

V2 adds:

```text
Phoenix traces
    ↓
Trace Curator
    ↓
Trace2Skill Adapter
    ↓
Candidate
    ↓
Eval Gate
```

---

# 5. Repository Layout

```text
skill-factory/
├── apps/
│   ├── web/                       # Next.js
│   └── api/                       # FastAPI
│
├── workers/
│   ├── main.py
│   ├── job_runner.py
│   ├── workspace.py
│   └── handlers/
│       ├── distill_repo.py
│       ├── distill_open_world.py
│       ├── fuse.py
│       ├── personalize.py
│       ├── evaluate.py
│       ├── export_skill.py
│       ├── refresh.py             # V2
│       ├── curate_trace.py        # V2
│       └── evolve.py              # V2
│
├── core/
│   ├── registry/
│   ├── lineage/
│   ├── provenance/
│   ├── releases/
│   ├── evidence/
│   ├── evals/
│   └── curation/                  # V2
│
├── adapters/
│   ├── base.py
│   ├── arex/
│   ├── skillalchemy/
│   ├── skillcreator/
│   ├── phoenix/
│   ├── promptfoo/
│   └── trace2skill/               # V2
│
├── schemas/
│   ├── skill.py
│   ├── source.py
│   ├── evidence.py
│   ├── job.py
│   ├── eval.py
│   ├── trace.py
│   └── release.py
│
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── fixtures/
│   └── e2e/
│
├── docker/
│   └── phoenix/
│
├── scripts/
├── .env.example
├── docker-compose.yml
└── README.md
```

---

# 6. Upstream Engine Contracts

The system must not expose upstream engine-specific data structures directly to the rest of the application.

All engines implement adapters.

## 6.1 Common adapter interface

Pseudo-interface:

```python
class SkillEngineAdapter(Protocol):
    name: str

    async def healthcheck(self) -> EngineHealth:
        ...

    async def run(
        self,
        job: SkillJob,
        workspace: Path,
    ) -> EngineResult:
        ...

    async def normalize(
        self,
        result: EngineResult,
    ) -> NormalizedSkillArtifact:
        ...
```

Common `EngineResult`:

```json
{
  "engine": "skillalchemy",
  "engine_version": "string|null",
  "exit_code": 0,
  "stdout_path": "...",
  "stderr_path": "...",
  "raw_output_path": "...",
  "artifacts": [],
  "metadata": {}
}
```

## 6.2 AREX adapter

Input:

```json
{
  "repo_url": "https://github.com/...",
  "ref": "optional branch/tag/commit",
  "objective": "optional"
}
```

Output:

- Skill directory/directories;
- source commit/ref when obtainable;
- discovered license metadata;
- engine logs.

V1 may support one selected output Skill per job.

## 6.3 SkillAlchemy adapter

Modes:

```text
create
fuse
```

Create input:

```json
{
  "brief": "...",
  "source_preferences": [],
  "constraints": []
}
```

Fuse input:

```json
{
  "parent_skill_version_ids": ["...", "..."],
  "fusion_objective": "...",
  "constraints": []
}
```

The adapter materializes parent Skill directories inside an isolated workspace before invocation.

## 6.4 Skill Creator adapter

Modes:

```text
create
improve
eval
benchmark
```

V1 priority:

```text
improve
eval
benchmark
```

Inputs may include:

- baseline Skill;
- candidate Skill;
- eval dataset;
- personal evidence;
- model/provider settings.

The adapter must map native Skill Creator eval/history results into the canonical eval schema.

## 6.5 Phoenix adapter

Responsibilities:

- create/query trace references;
- attach trace IDs to Skill version / execution;
- create/use datasets where appropriate;
- store experiment/eval references.

Phoenix is not the canonical Skill Registry.

## 6.6 Promptfoo adapter

Responsibilities:

- materialize repeatable regression config;
- execute selected eval suites;
- parse JSON output;
- return normalized case results.

V1 may keep Promptfoo as optional behind a feature flag, but the adapter interface must exist.

## 6.7 Trace2Skill adapter — V2

Do not depend on SpreadsheetBench internals.

Input contract:

```json
{
  "base_skill_version_id": "...",
  "curated_trace_ids": ["..."],
  "learning_objective": "...",
  "constraints": []
}
```

Output:

```json
{
  "candidate_artifact": "...",
  "proposed_changes": [
    {
      "type": "add|modify|remove",
      "target": "rule/procedure/reference",
      "summary": "...",
      "evidence_trace_ids": ["..."]
    }
  ],
  "analysis_artifacts": []
}
```

---

# 7. Canonical Skill Package

Each registered version must normalize to:

```text
artifact/
├── SKILL.md
├── references/              # optional
├── scripts/                 # optional
├── assets/                  # optional
├── evals/                   # optional
├── manifest.json
├── provenance.json
└── CHANGELOG.md
```

## 7.1 `manifest.json`

Required example:

```json
{
  "schema_version": "1.0",
  "skill_id": "uuid",
  "skill_slug": "topic-selection",
  "version": "1.2.0",
  "name": "Topic Selection",
  "description": "...",
  "layer_type": "compiled",
  "status": "candidate",
  "created_by_engine": "skillcreator",
  "created_from_job_id": "uuid",
  "parent_versions": [
    {
      "version_id": "uuid",
      "relation": "personalized_from"
    }
  ],
  "compatibility": {},
  "created_at": "ISO8601"
}
```

`layer_type` values:

```text
core
domain
personal
compiled
```

V1 can use `compiled` most often while retaining layer metadata.

## 7.2 `provenance.json`

Example:

```json
{
  "sources": [
    {
      "source_id": "uuid",
      "type": "github_repo",
      "uri": "https://github.com/example/repo",
      "ref": "commit-sha",
      "license": "MIT",
      "captured_at": "ISO8601"
    }
  ],
  "rules": [
    {
      "rule_key": "claims.require_evidence",
      "summary": "Downgrade unsupported claims",
      "evidence_ids": ["evidence-1", "evidence-2"],
      "confidence": "high"
    }
  ]
}
```

---

# 8. Database Model

Use Supabase Postgres.

IDs are UUIDs.

## 8.1 `skills`

```text
id
slug UNIQUE
name
description
created_at
updated_at
archived_at nullable
```

## 8.2 `skill_versions`

```text
id
skill_id FK
version
layer_type
status
artifact_storage_path
artifact_hash
created_by_engine
created_from_job_id
created_at
promoted_at nullable
```

Constraint:

```text
UNIQUE(skill_id, version)
```

## 8.3 `skill_lineage`

```text
id
parent_version_id
child_version_id
relation
created_at
```

`relation`:

```text
distilled_from
fused_from
personalized_from
evolved_from
refreshed_from
derived_from
```

## 8.4 `sources`

```text
id
source_type
uri
repo_ref nullable
content_hash nullable
license nullable
metadata jsonb
captured_at
```

`source_type`:

```text
github_repo
web_source
document
manual
demonstration
production_trace
existing_skill
```

## 8.5 `skill_version_sources`

```text
skill_version_id
source_id
role
evidence_grade nullable
```

Role examples:

```text
primary
supporting
example
contradicting
```

## 8.6 `evidence_items`

```text
id
skill_id nullable
evidence_type
title
content
rationale nullable
rating nullable
metadata jsonb
created_at
```

`evidence_type`:

```text
demonstration
correction
choice
good_example
bad_example
preference
decision_rationale
```

## 8.7 `jobs`

```text
id
job_type
engine
status
input jsonb
output jsonb nullable
workspace_path nullable
started_at nullable
finished_at nullable
error nullable
created_at
```

`status`:

```text
queued
running
succeeded
failed
cancelled
```

## 8.8 `eval_datasets`

```text
id
skill_id nullable
name
dataset_type
version
split
created_at
```

`dataset_type`:

```text
functional
personal
regression
generalization
trigger
```

`split`:

```text
dev
holdout
```

## 8.9 `eval_cases`

```text
id
dataset_id
prompt
expected_output nullable
expectations jsonb
files jsonb
tags jsonb
source_evidence_id nullable
created_at
```

## 8.10 `eval_runs`

```text
id
skill_version_id
baseline_version_id nullable
dataset_id
engine
model
status
summary jsonb
started_at
finished_at
```

## 8.11 `eval_case_results`

```text
id
eval_run_id
eval_case_id
passed nullable
score nullable
grader_output jsonb
candidate_output_path nullable
baseline_output_path nullable
latency_ms nullable
cost nullable
```

## 8.12 `releases`

```text
id
skill_id
skill_version_id
environment
release_state
released_at
superseded_at nullable
rollback_from_release_id nullable
```

V1 environment:

```text
production
```

V2 adds:

```text
shadow
canary
```

## 8.13 `executions`

```text
id
skill_version_id
external_trace_id nullable
input_summary
output_summary nullable
status
user_rating nullable
created_at
```

## 8.14 V2: `trace_curation`

```text
id
execution_id
root_cause
learnable
learning_category nullable
confidence
curator_type
human_approved
notes nullable
created_at
```

`root_cause`:

```text
skill
model
tool
infrastructure
input
context
external_change
evaluation
unknown
```

`learning_category`:

```text
skill_failure
preference_mismatch
missing_reusable_procedure
reusable_success_pattern
reusable_recovery_pattern
```

---

# 9. Versioning

Use semantic-like versions but do not automatically infer compatibility.

Recommended:

```text
0.x.y = experimental/draft
1.x.y+ = promoted lineage
```

Factory behavior:

- every engine output that changes Skill content creates a new immutable version;
- never mutate a promoted artifact;
- versions must retain parent lineage;
- user can attach a human changelog.

Automatic version suggestion:

```text
patch:
small instruction/eval/resource change

minor:
new capability/procedure

major:
manual user choice for incompatible redesign
```

User can override.

---

# 10. Job Workspace Isolation

Each job gets:

```text
/workspaces/{job_id}/
├── input/
├── engine/
├── output/
└── logs/
```

Requirements:

- one job cannot read another workspace by default;
- secret values must never be written into artifact files;
- environment variables may be passed to subprocess;
- capture command, exit code, stdout, stderr;
- preserve failed workspace until user chooses cleanup;
- successful raw workspace may be garbage-collected after configurable retention once normalized artifacts are stored.

---

# 11. V1 Features

## 11.1 Dashboard

Show:

- total Skills;
- production Skills;
- candidates awaiting eval;
- failed jobs;
- latest activity.

Acceptance:

- loads from Supabase;
- no hard-coded demo data in production mode.

## 11.2 Skills Library

List fields:

- name;
- slug;
- production version;
- latest candidate;
- source type;
- last modified.

Actions:

- open;
- create;
- import;
- archive.

## 11.3 Skill Detail

Tabs:

```text
Overview
Versions
Sources
Evidence
Evals
Releases
Files
Activity
```

Must show lineage graph in a simple form.

V1 graph may be a chronological tree/list rather than a visual graph library.

## 11.4 Create from Repo

Form:

```text
Repository URL *
Ref optional
Objective optional
```

Flow:

1. validate URL;
2. create job;
3. AREX adapter executes;
4. normalize result;
5. preview;
6. user registers Skill.

Must show raw engine logs.

## 11.5 Create from Requirement

Form:

```text
Skill brief *
Optional constraints
Optional source preferences
```

Flow:

1. create SkillAlchemy job;
2. show progress/log;
3. normalize artifact;
4. show research/provenance if available;
5. register version.

## 11.6 Import Existing Skill

Input:

- local `.zip`, or
- uploaded directory archive.

Validation:

- `SKILL.md` required;
- parse frontmatter where possible;
- preserve additional files;
- generate missing factory `manifest.json`;
- do not rewrite upstream `SKILL.md` unless explicitly requested.

## 11.7 Fuse

User selects 2–5 source versions.

Inputs:

```text
fusion objective *
constraints optional
new Skill name
```

Result:

- new Skill/version;
- lineage relation `fused_from` for every parent;
- source provenance preserved/merged.

## 11.8 Personal Evidence

Evidence editor supports:

### Demonstration

```text
task
what I did
why
result optional
```

### Correction

```text
original behavior
corrected behavior
reason
```

### Choice

```text
context
options
selected option
reason
rejected reasons optional
```

### Good/bad example

```text
input/context
artifact/output
label
reason
```

Every evidence item can be:

- included in personalization;
- included in eval dataset;
- both;
- neither/archive.

## 11.9 Eval Dataset Builder

User can build:

```text
Functional Dev
Functional Holdout
Personal Dev
Personal Holdout
Regression
Generalization
Trigger
```

V1 does not require every Skill to have every dataset, but promotion requirements are configurable.

Minimum recommended first promotion:

- ≥5 functional cases;
- ≥5 personal cases when personalized;
- ≥3 regression cases if a prior production version exists.

The UI must clearly mark **dev** vs **holdout**.

Do not let an automated improve job write into the holdout dataset.

## 11.10 Personalize / Improve

Input:

- baseline Skill version;
- selected personal evidence;
- selected development eval datasets;
- engine/model settings.

Flow:

```text
baseline snapshot
→ Skill Creator Improve
→ candidate artifact
→ register candidate
→ automatically launch selected dev eval
```

The candidate is not production.

## 11.11 Evaluate

Allow:

### Single version eval

```text
Skill Version + Dataset
```

### Candidate vs baseline

```text
Candidate + Baseline + Dataset
```

Normalized result:

- pass rate;
- case scores;
- candidate vs baseline win/loss/tie where supported;
- failures;
- latency/cost where obtainable.

## 11.12 Eval Gate

V1 gate policy object:

```json
{
  "requirements": [
    {
      "dataset_type": "functional",
      "split": "holdout",
      "min_pass_rate": 0.8
    },
    {
      "dataset_type": "personal",
      "split": "holdout",
      "min_pass_rate": 0.8,
      "required_if": "has_personal_layer"
    }
  ],
  "must_not_regress": true
}
```

Gate output:

```text
PASS
FAIL
INCOMPLETE
```

Only `PASS` is promotable.

User may have an explicit manual override action, but override must:

- require a reason;
- be logged;
- never silently change eval results.

## 11.13 Promote

Requirements:

- candidate registered;
- gate = PASS, or explicit logged override;
- immutable artifact exists;
- artifact hash verified.

Action:

- previous production release becomes superseded;
- new production pointer created;
- event recorded.

## 11.14 Rollback

User selects a previously promoted version.

System:

- creates release event pointing production to prior version;
- does not modify artifacts;
- records rollback reason.

## 11.15 Export

Export `.zip` with:

```text
SKILL.md
references/
scripts/
assets/
evals/           optional
manifest.json
provenance.json
CHANGELOG.md
```

Option:

```text
Portable mode
```

Portable mode may omit factory-only internal metadata not needed by external agents, but provenance should remain when safe.

## 11.16 Phoenix Trace Linkage

V1 must at minimum allow:

- execution record with Skill version;
- Phoenix external trace ID;
- open/copy trace reference;
- user rating;
- feedback text.

Instrumentation may be implemented first in the factory's test execution path.

---

# 12. V2 Features

## 12.1 Trace Curator

Input:

- execution;
- trace;
- outcome;
- user feedback;
- optional grader result.

Stage 1 — Outcome attribution:

```text
skill
model
tool
infrastructure
input
context
external_change
evaluation
unknown
```

Stage 2 — Learnability filter:

```text
learnable = true/false
```

If true:

```text
skill_failure
preference_mismatch
missing_reusable_procedure
reusable_success_pattern
reusable_recovery_pattern
```

V2 default:

- LLM proposes classification;
- human approves/rejects;
- no full auto-learning by default.

## 12.2 Curated Trace Set

User can create evolution batches from approved learnable traces.

Filters:

- Skill version;
- category;
- rating;
- failure/success;
- date range;
- tags.

## 12.3 Trace2Skill Evolution

Flow:

```text
production/base Skill
+ approved trace batch
       ↓
Trace2Skill generic adapter
       ↓
candidate
+ proposed change list
+ evidence trace links
```

Every proposed change must retain the trace IDs that motivated it.

## 12.4 Evolution candidate review

UI must show a semantic change summary.

Example:

```text
ADD
"Before accepting a trend, check whether firsthand evidence is available."

Evidence:
trace_10
trace_14
trace_21
```

User can:

- accept full candidate;
- reject;
- optionally request another evolution run.

V2 does not require interactive per-line merge editing.

## 12.5 Strong Eval Gate

V2 default promotion gate:

```text
Functional Holdout
Personal Holdout
Regression
Generalization
Trigger
```

Optional:

```text
Cost
Latency
```

No production promotion if:

- holdout regresses beyond configured tolerance;
- regression suite fails protected cases;
- generalization degrades beyond threshold.

## 12.6 Upstream Refresh

For AREX-backed Skills:

```text
Source repo changed
→ refresh job
→ Base Skill candidate
→ compare with current Base
→ preserve Personal layer
→ re-compose
→ full eval gate
```

V2 should support manual refresh first.

Scheduled monitoring is optional.

## 12.7 Layer Composition

Introduce real layer objects:

```text
Core Skill Version
Domain Skill Version
Personal Layer Version
```

Compiled Skill references these parent layers.

A personal layer should be reusable across compatible descendants where explicitly selected.

## 12.8 Shadow / Canary

States:

```text
candidate
passed
shadow
canary
production
archived
```

Shadow:

- receives duplicate evaluation traffic where feasible;
- does not control user-visible output.

Canary:

- receives a configurable fraction of eligible tasks;
- compare outcome to production baseline.

V2 can implement canary only inside Factory-managed execution paths.

## 12.9 Rollback recommendation

System may recommend rollback if:

- error rate exceeds threshold;
- regression score degrades;
- user ratings degrade.

Automatic rollback is out of scope unless explicitly enabled in a future version.

---

# 13. Eval Model

## 13.1 Separation rules

Development data and holdout data must be distinct.

Rules:

1. Skill Creator Improve can see dev cases.
2. Trace2Skill may use curated production traces.
3. Holdout cases must not be provided to the optimizer.
4. Regression protected cases are immutable by automated optimization.
5. Human can explicitly move/edit cases, but all changes are versioned.

## 13.2 Dataset versioning

Every dataset change creates a new dataset version.

Eval run stores the exact dataset version ID.

Never compare scores across different dataset versions without labeling the difference.

## 13.3 Grader types

Support:

```text
deterministic
LLM judge
human
hybrid
```

Store grader metadata:

```text
model
prompt/version
temperature if applicable
code/version if deterministic
```

## 13.4 Candidate comparison

Where possible, use blind comparison.

Store:

```text
candidate wins
baseline wins
ties
```

Do not rely only on one aggregate LLM score.

---

# 14. Provenance Requirements

Every generated version must answer:

```text
Who/what created this?
From which parent versions?
From which sources?
From which personal evidence?
From which production traces?
Which evals approved it?
```

V1 minimum:

- source-level provenance;
- parent-version lineage;
- engine/job origin.

V2:

- rule/procedure-level evidence links where obtainable.

---

# 15. Release Policy

## 15.1 V1 default

Promotion is human-approved.

```text
Eval PASS
   ↓
User Promote
```

## 15.2 Manual override

Allowed but logged:

```text
actor
reason
timestamp
failed requirements
```

## 15.3 Production pointer

A Skill has max one active production release for the default environment.

---

# 16. API Requirements

Exact endpoint names may change, but capabilities must exist.

## 16.1 Skills

```text
GET    /skills
POST   /skills
GET    /skills/{skill_id}
POST   /skills/import
POST   /skills/{skill_id}/archive
```

## 16.2 Versions

```text
GET    /skills/{skill_id}/versions
GET    /versions/{version_id}
GET    /versions/{version_id}/files
POST   /versions/{version_id}/export
```

## 16.3 Jobs

```text
POST   /jobs/distill/repo
POST   /jobs/distill/open-world
POST   /jobs/fuse
POST   /jobs/personalize
POST   /jobs/evaluate
GET    /jobs/{job_id}
GET    /jobs/{job_id}/logs
POST   /jobs/{job_id}/cancel
```

V2:

```text
POST   /jobs/curate
POST   /jobs/evolve
POST   /jobs/refresh
```

## 16.4 Evidence

```text
GET    /skills/{skill_id}/evidence
POST   /skills/{skill_id}/evidence
PATCH  /evidence/{evidence_id}
DELETE /evidence/{evidence_id}
```

## 16.5 Evals

```text
GET    /eval-datasets
POST   /eval-datasets
POST   /eval-datasets/{id}/cases
POST   /eval-runs
GET    /eval-runs/{id}
GET    /versions/{id}/eval-summary
```

## 16.6 Releases

```text
POST   /versions/{version_id}/promote
POST   /skills/{skill_id}/rollback
GET    /skills/{skill_id}/releases
```

---

# 17. Security

V1 is local-first but must still follow basic secret hygiene.

Requirements:

- secrets only through environment variables / secret store;
- never serialize API keys into Skill artifacts;
- redact common secret patterns from logs;
- restrict subprocess working directory;
- validate uploaded archives against path traversal;
- limit archive size;
- do not execute imported Skill scripts automatically;
- scripts execute only in explicit engine/test jobs;
- show user when a Skill contains executable scripts;
- retain source license metadata.

V2 should introduce stronger sandboxing before allowing arbitrary third-party scripts in automated production flows.

---

# 18. Configuration

`.env.example` should document:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_STORAGE_BUCKET

PHOENIX_ENDPOINT

OPENAI_API_KEY
ANTHROPIC_API_KEY
GEMINI_API_KEY

AREX_DISCO_BIN
CLAUDE_CODE_BIN
CODEX_BIN
PROMPTFOO_BIN

WORKSPACE_ROOT
JOB_POLL_INTERVAL
LOG_RETENTION_DAYS
```

Do not require every model provider simultaneously.

---

# 19. Local Development

Target command:

```bash
docker compose up -d
```

Should start:

- Phoenix;
- optional local dependencies.

Then:

```bash
pnpm dev:web
python -m apps.api
python -m workers.main
```

Alternative root helper scripts are acceptable.

Provide a setup checker:

```bash
python scripts/doctor.py
```

Doctor checks:

- DB connection;
- Storage;
- Phoenix;
- AREX CLI;
- configured agent CLI for SkillAlchemy/Skill Creator;
- Promptfoo if enabled;
- required API keys without printing them.

---

# 20. UX Pages

V1 required pages:

```text
/
  Dashboard

/skills
  Skills library

/skills/new
  Create:
  - Repo
  - Requirement
  - Import

/skills/{id}
  Overview
  Versions
  Sources
  Evidence
  Evals
  Releases
  Files

/jobs/{id}
  status + logs + artifacts

/fusion/new
  choose parents + objective

/evals
  datasets + runs

/settings
  engines + provider health
```

V2:

```text
/traces
/curation
/evolution
```

---

# 21. Functional Acceptance Criteria — V1

V1 is complete only when all of the following work end to end.

## AC-V1-01 — Repo distillation

Given a valid supported GitHub repository:

- AREX job starts;
- logs are visible;
- at least one Skill artifact is returned;
- normalized artifact contains `SKILL.md`;
- version is stored;
- repo URL is recorded;
- commit/ref is recorded when available.

## AC-V1-02 — Open-world Skill creation

Given a requirement brief:

- SkillAlchemy executes;
- generated Skill is normalized;
- output can be previewed;
- source/provenance metadata is stored when available;
- draft version is registered.

## AC-V1-03 — Fusion

Given two registered Skill versions:

- fusion job succeeds;
- child Skill is created;
- both parent lineage edges exist;
- source provenance is not silently lost.

## AC-V1-04 — Personal evidence

User can create at least:

- correction;
- choice;
- good example;
- bad example.

Data persists and can be selected for personalization/eval.

## AC-V1-05 — Personalization

Given a baseline Skill and development evidence:

- Skill Creator Improve job produces a candidate;
- baseline remains unchanged;
- candidate lineage includes `personalized_from`;
- change summary is visible.

## AC-V1-06 — Eval

Given candidate + dataset:

- eval runs;
- per-case results persist;
- aggregate result is shown;
- candidate/baseline comparison is stored when requested.

## AC-V1-07 — Holdout protection

Automated improve job cannot read a holdout dataset through the normal application path.

## AC-V1-08 — Promote

A passing candidate can be promoted.

The previous production artifact remains immutable and available.

## AC-V1-09 — Failed gate

A failing candidate cannot be promoted normally.

Manual override requires a reason and creates an audit event.

## AC-V1-10 — Rollback

User can restore a previous production version without editing artifacts.

## AC-V1-11 — Export

Any registered version can be exported as a valid archive containing `SKILL.md`.

## AC-V1-12 — Observability

At least one test execution can:

- create an `executions` row;
- write/associate a Phoenix trace ID;
- receive user rating/feedback.

## AC-V1-13 — Restart safety

After restarting UI/API/worker:

- registered Skills;
- jobs;
- evals;
- releases;
- evidence

remain available.

---

# 22. Functional Acceptance Criteria — V2

## AC-V2-01 — Trace attribution

An execution can be classified by root cause and learnability.

## AC-V2-02 — Human curation

No trace enters Trace2Skill unless approved under default configuration.

## AC-V2-03 — Generic Trace2Skill

Trace2Skill adapter can evolve a non-spreadsheet demo Skill from canonical trace inputs.

## AC-V2-04 — Evidence-linked patch

Every generated evolution candidate contains trace/evidence links for proposed changes.

## AC-V2-05 — Eval before promote

Trace2Skill output cannot directly become production.

## AC-V2-06 — Held-out evaluation

Candidate must be evaluated on a dataset not exposed to the optimizer.

## AC-V2-07 — Generalization protection

A personalized/evolved candidate that improves personal score but breaches generalization threshold fails the gate.

## AC-V2-08 — Upstream refresh

An AREX-backed base Skill can refresh from an updated repo and create a candidate without deleting the existing production/personal layer.

## AC-V2-09 — Re-composition

A refreshed base can be combined with the existing personal layer to produce a new candidate.

## AC-V2-10 — Shadow/canary state

Release state machine supports at least `shadow` and `canary`.

## AC-V2-11 — Provenance

User can inspect:

```text
candidate
→ parent
→ supporting traces
→ eval runs
→ release
```

## AC-V2-12 — Rollback history

After a V2 release and rollback, all release transitions remain auditable.

---

# 23. Non-Functional Requirements

## Reliability

- a failed engine job cannot corrupt an existing Skill version;
- artifact registration occurs only after normalization succeeds;
- file hash used to verify immutable artifact.

## Maintainability

- upstream engines accessed through adapters;
- no business logic inside UI components;
- schemas have migrations;
- adapters have integration tests with fixtures.

## Portability

- generated Skills remain usable outside Skill Factory;
- factory-specific metadata must not make `SKILL.md` unusable.

## Auditability

All of these are immutable/auditable:

- version creation;
- parent lineage;
- eval run;
- promotion;
- rollback;
- manual override.

## Cost

V1 must allow selecting cheaper models for:

- research;
- improve;
- eval judging.

No provider hard-coding.

---

# 24. Testing Strategy

## 24.1 Unit

Test:

- normalization;
- manifest generation;
- version increment;
- lineage;
- gate policy;
- archive validation;
- secret redaction.

## 24.2 Adapter integration

Use fixture mode where possible.

Each adapter needs:

```text
healthcheck test
success fixture
failure fixture
normalization fixture
```

CI must not require paid API calls.

Live integration tests are opt-in.

## 24.3 E2E golden path

Automated/local E2E:

```text
Import fixture Skill
→ add personal correction
→ create candidate via mock engine
→ evaluate
→ PASS
→ promote
→ export
→ rollback
```

External engine smoke tests are separate.

---

# 25. Implementation Phases

## Phase V1.0 — Foundation

Build:

- monorepo;
- Supabase schema/migrations;
- Storage;
- API;
- worker/job queue;
- canonical artifact format;
- registry/version/lineage/provenance;
- basic UI.

Exit:

- import fixture Skill;
- version;
- promote;
- rollback;
- export.

## Phase V1.1 — Creation Engines

Add:

- AREX adapter;
- SkillAlchemy adapter;
- create-from-repo;
- create-from-requirement;
- fusion.

Exit:

- two independent source routes work end to end.

## Phase V1.2 — Personalization + Eval

Add:

- evidence editor;
- eval datasets;
- Skill Creator adapter;
- improve;
- baseline comparison;
- eval gate;
- Promptfoo optional regression adapter.

Exit:

- general Skill → personalized candidate → evaluated → promoted.

## Phase V1.3 — Observability

Add:

- Phoenix deployment;
- test execution trace linkage;
- rating/feedback;
- dataset/experiment references if useful.

Exit:

- promoted Skill can produce a trace associated with exact version.

### V1 Release Definition

V1 is released after V1.0–V1.3 acceptance criteria pass.

---

## Phase V2.0 — Trace Curation

Add:

- execution feedback workflow;
- outcome attribution;
- learnability classification;
- human approval queue;
- curated trace sets.

## Phase V2.1 — Generic Trace2Skill

Add:

- canonical trajectory format;
- adapter/refactor;
- patch proposal output;
- candidate generation;
- evidence trace links.

## Phase V2.2 — Strong Governance

Add:

- dev/holdout enforcement;
- regression/generalization/trigger gates;
- shadow/canary;
- richer release comparison.

## Phase V2.3 — Knowledge Refresh

Add:

- AREX refresh;
- source diff;
- base layer refresh;
- preserve personal layer;
- re-composition;
- full eval.

### V2 Release Definition

V2 is released when production traces can safely generate an evaluated candidate without any direct production overwrite.

---

# 26. What NOT to build first

Do not block V1 on:

- fancy graph visualization;
- multi-user auth;
- public marketplace;
- dozens of model providers;
- autonomous trace learning;
- Kubernetes;
- distributed queue;
- custom vector DB;
- custom observability UI;
- custom LLM eval framework;
- training/fine-tuning;
- perfect rule-level provenance extraction.

Start with a working lifecycle.

---

# 27. Coding Constraints for Codex

1. Prefer small adapters over modifying upstream repositories.
2. Do not vendor entire upstream repos.
3. Pin/test engine versions where possible.
4. Never let engine-specific schemas leak into core database schema.
5. Never overwrite a registered artifact.
6. All new generated artifacts create a version.
7. Never automatically promote.
8. Keep holdout data inaccessible to optimization workflows.
9. Do not execute untrusted imported scripts during import.
10. Add tests with each lifecycle transition.
11. Prefer simple readable code over framework-heavy abstractions.
12. V1 is single-user/local-first; do not prematurely build RBAC/multi-tenancy.

---

# 28. Initial Technical Decisions

Use these unless implementation discovers a concrete blocker.

```text
Frontend:       Next.js + TypeScript
API:            FastAPI + Python
Database:       Supabase Postgres
Artifact store: Supabase Storage
Observability:  Arize Phoenix
Regression:     Promptfoo
Repo distill:   AREX / DisCo
Open research:  SkillAlchemy
Improve/eval:   Anthropic Skill Creator
Evolution V2:   Trace2Skill, genericized
Queue V1:       Postgres-backed polling worker
Deploy V1:      local Mac mini / Docker where suitable
```

---

# 29. First Demo Scenario

Use one controlled Skill to prove the system.

Recommended demo:

```text
"AI creator topic selection"
```

Flow:

1. use SkillAlchemy to create a general topic-selection Skill;
2. optionally fuse a repo-derived research/data capability;
3. add 10 personal decision cases;
4. split:
   - 6 dev;
   - 4 holdout;
5. use Skill Creator Improve;
6. evaluate baseline vs personalized candidate;
7. promote candidate if gate passes;
8. execute several real tasks;
9. capture Phoenix traces;
10. V2 later curates those traces and evolves the Skill.

This demo exercises methodology understanding rather than only technical repo usage.

---

# 30. Final Product Invariant

At all times:

```text
Production Skill
≠ latest generated Skill
```

Production Skill must mean:

```text
A specific immutable version
with known lineage
with known evidence
with recorded evaluation
with an explicit release decision
and a safe rollback target.
```

That invariant is the foundation of the entire Skill Factory.
