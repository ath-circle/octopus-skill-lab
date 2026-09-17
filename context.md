# Skill Factory / OPC — Project Context

> **Status:** Architecture context for implementation  
> **Date:** 2026-09-17  
> **Primary goal:** Build a local-first Skill Factory that can create, fuse, personalize, evaluate, version, release, and later continuously improve Agent Skills.  
> **Audience:** Codex / Claude Code / engineering contributors  
> **Language:** Product/UI may be bilingual later; engineering artifacts and identifiers should use English.

---

## 1. Why this project exists

The project is not another prompt manager and not a generic multi-agent chat UI.

The core idea is:

> Treat an Agent Skill as a versioned, testable, evidence-backed software artifact with its own lifecycle.

The desired lifecycle is:

```text
Source
  ↓
Distill / Research
  ↓
Fuse / Compose
  ↓
Personalize
  ↓
Evaluate
  ↓
Promote
  ↓
Production Use
  ↓
Trace + Feedback
  ↓
Learn
  ↓
Candidate Update
  ↓
Evaluate Again
  ↓
Promote / Reject / Roll Back
```

The long-term OPC (multi-agent workbench) can consume these Skills, but the Skill Factory should remain a separable subsystem.

---

## 2. Core mental model

A Skill is not only `SKILL.md`.

A production-quality Skill may contain:

```text
skill-name/
├── SKILL.md
├── references/
├── scripts/
├── assets/
├── evals/
├── manifest.json
├── provenance.json
└── CHANGELOG.md
```

The contents have different responsibilities:

- `SKILL.md`: routing, workflow, decision procedure, guardrails, recovery, verification.
- `references/`: deeper domain knowledge loaded only when needed.
- `scripts/`: deterministic or repetitive operations.
- `assets/`: templates and output resources.
- `evals/`: test cases and evaluation expectations.
- `manifest.json`: machine-readable identity, version, lineage, compatibility.
- `provenance.json`: where important procedures/rules came from.
- `CHANGELOG.md`: what changed and why.

The Skill Factory must preserve **progressive disclosure** rather than collapsing everything into one huge prompt.

---

## 3. The four loops

The project should be designed around four independent but connected loops.

### 3.1 Knowledge Loop

```text
External repo / docs / public knowledge / requirement
        ↓
Distillation / research
        ↓
Base / Domain Skill
        ↓
Fusion / composition
        ↓
General Skill
        ↓
Upstream changes later
        ↓
Refresh
```

Purpose: keep general knowledge current and reusable.

### 3.2 Personal Learning Loop

```text
General Skill
    ↓
Demonstrations / corrections / choices / good-bad examples
    ↓
Personalization
    ↓
Production
    ↓
Trace + outcome + user feedback
    ↓
Curate learnable traces
    ↓
Skill evolution
```

Purpose: learn the user's actual decision process rather than merely adding style instructions.

### 3.3 Release / Governance Loop

```text
Candidate Skill
    ↓
Development Eval
    ↓
Held-out Eval
    ↓
Regression / Generalization / Trigger Eval
    ↓
PASS ──→ Promote
FAIL ──→ Analyze → Revise / Discard
```

Purpose: no automatically generated Skill change is trusted merely because an LLM proposed it.

### 3.4 Evidence / Provenance Loop

Every important rule should be traceable.

Example:

```json
{
  "rule": "Downgrade claim strength when evidence is weak.",
  "origin": ["personal_case_031", "trace_891", "trace_933"],
  "introduced_in": "v2.4",
  "reason": "Repeated correction across three tasks",
  "confidence": "high",
  "eval_cases": ["personal_17", "regression_42"]
}
```

Purpose: prevent unexplained prompt accretion and make later deletion/rollback defensible.

---

## 4. Two entry routes for creating a Skill

There are two primary creation routes.

### Route A — Existing implementation knowledge exists

Example:

- GitHub repository
- working open-source library
- technical project with code and docs

Preferred engine:

**AREX-Skill / DisCo**

Goal:

```text
Repository
  ↓
Repo operating knowledge
  ↓
Normalized executable Skill
```

This should capture not only "what the repository does" but how to use, validate, and recover.

### Route B — The capability is underspecified or unique

Example:

- "Build a Skill for selecting AI creator topics using evidence, audience maturity, and commercial value."
- "Build a Skill for reviewing furniture marketplace listings with platform-specific rules."
- no clean upstream repository exists

Preferred engine:

**SkillAlchemy**

Goal:

```text
Underspecified requirement
   ↓
Discover implicit dimensions
   ↓
Research evidence
   ↓
Extract procedures
   ↓
Determine scope
   ↓
Compile Skill
```

SkillAlchemy is also the preferred initial **fusion/synthesis engine** when multiple Skills must be combined.

---

## 5. Fusion vs composition

V1 may use SkillAlchemy fusion to generate a practical merged Skill.

However, the long-term architecture should avoid permanently flattening all knowledge into one giant Skill.

Preferred conceptual layers:

```text
Core
  +
Domain
  +
Personal
  +
Task Context
  ↓
Execution
```

Example:

```text
topic-selection/
├── core/
│   └── general topic selection methodology
├── domain/
│   └── AI creator / social media knowledge
├── personal/
│   └── Yuan-specific preferences and decision rules
├── cases/
└── evals/
```

When portability is required, the system may compile these layers into an exportable Skill package.

The data model must support layering/lineage from V1 even if runtime composition is implemented in V2.

---

## 6. Personalization philosophy

Personalization does **not** mean:

```text
"User prefers practical content."
```

The strongest evidence is a collection of actual choices, corrections, and demonstrations.

Example:

```text
Case:
GPT releases a new memory feature.

Candidates:
A. Feature summary
B. Full tutorial
C. Test whether memory can replace a CRM follow-up workflow
D. Sensational announcement

Chosen:
C

Reason:
Business implication + experiment + differentiation.

Rejected:
A — commodity information
B — saturated
D — unsupported clickbait
```

Personalization evidence sources:

1. demonstrations;
2. user corrections;
3. explicit choices among alternatives;
4. good/bad examples;
5. rationale for decisions;
6. production feedback;
7. repeated recovery patterns.

**Anthropic Skill Creator** is used as a development/evaluation/improvement harness. It does not magically discover the user's preferences without evidence.

---

## 7. Production learning philosophy

Production traces are not automatically lessons.

Bad pipeline:

```text
Production Trace
   ↓
Trace2Skill
```

Required pipeline:

```text
Production Trace
   ↓
Outcome / Rating / Feedback
   ↓
Outcome Attribution
   ↓
Learnability Filter / Trace Curator
   ↓
Trace2Skill
```

Failures may be caused by:

- infrastructure failure;
- API timeout;
- tool failure;
- missing permission;
- bad input;
- missing context;
- external-world change;
- model randomness;
- evaluation error;
- genuine Skill failure;
- personal preference mismatch.

Only reusable, learnable causes should update Skills.

Examples of learnable categories:

- `skill_failure`
- `preference_mismatch`
- `missing_reusable_procedure`
- `reusable_success_pattern`
- `reusable_recovery_pattern`

---

## 8. Evaluation philosophy

Trace2Skill can include task-specific evaluation in its research workflow, but it is **not the Skill Factory's universal Eval Platform**.

The Skill Factory needs independent evaluation.

Minimum evaluation dimensions:

1. **Functional** — did the Skill complete the task correctly?
2. **Personal** — did it make decisions consistent with the user's accepted examples?
3. **Regression** — did the new version break previously working behavior?
4. **Generalization** — did personalization overfit and make the Skill worse on legitimate unseen cases?
5. **Routing / Trigger** — did the Skill trigger when it should and stay inactive when it should not?
6. **Cost / Latency** — optional in early V1, important for V2.

Every learning system produces a **candidate**, never a production overwrite.

```text
candidate
  ↓
eval gate
  ├── PASS → promote
  └── FAIL → revise / discard
```

---

## 9. Upstream open-source components

Verified as of 2026-09-17.

### 9.1 AREX-Skill / DisCo

Repository:

https://github.com/VectorSpaceLab/AREX-Skill

Use for:

- GitHub repo → executable operating Skill
- repo-skill library
- source grounding
- repo refresh/provenance patterns

Important architectural decision:

**Do not vendor the entire repository into this project.** Use an adapter and invoke DisCo as an external engine.

### 9.2 SkillAlchemy

Repository:

https://github.com/agentsope/SkillAlchemy

Use for:

- open-world Skill creation;
- implicit requirement discovery;
- evidence-grounded procedure extraction;
- fusion of existing Skills;
- compilation of a new Skill package.

Important architectural decision:

Treat it as a capability-synthesis engine behind an adapter.

### 9.3 Anthropic Skill Creator

Repository / Skill:

https://github.com/anthropics/skills/tree/main/skills/skill-creator

Use for:

- create;
- improve;
- eval;
- benchmark;
- trigger-description optimization;
- baseline vs candidate comparisons.

Skill Creator defines eval/history schemas and supports bundled resources.

Important architectural decision:

Do not make the database or lifecycle dependent on Skill Creator's internal workspace format. Convert to/from the Skill Factory canonical schema.

### 9.4 Arize Phoenix

Repository:

https://github.com/Arize-ai/phoenix

Use for:

- OpenTelemetry-based traces;
- versioned datasets;
- evaluations;
- experiments;
- annotations;
- production debugging.

Important architectural decision:

Do not build a custom observability platform in V1.

### 9.5 Promptfoo

Repository:

https://github.com/promptfoo/promptfoo

Use for:

- deterministic/repeatable regression suites;
- CI evaluation;
- model/provider comparisons;
- optional later red-team suites.

Important architectural decision:

Promptfoo complements Phoenix. Phoenix is production observability/experimentation; Promptfoo is a repeatable CI gate.

### 9.6 Trace2Skill

Repository:

https://github.com/Qwen-Applications/Trace2Skill

Use for V2:

- analyze a pool of execution traces;
- propose trajectory-local Skill patches;
- consolidate patches;
- deepen an existing Skill or create from weak initial draft.

Important architectural decision:

**Do not integrate its SpreadsheetBench-specific application layer unchanged.**

Reuse/refactor the generic evolution ideas:

```text
curated traces
→ parallel analysis
→ patch proposals
→ conflict-aware consolidation
→ candidate Skill
```

Replace:

- benchmark-specific runner;
- spreadsheet-specific assumptions;
- official evaluator bindings;
- trajectory schema;
- dataset integration.

---

## 10. Build vs reuse decision

### Reuse through adapters

- AREX / DisCo
- SkillAlchemy
- Anthropic Skill Creator
- Phoenix
- Promptfoo

### Refactor heavily in V2

- Trace2Skill

### Build ourselves

- canonical Skill schema;
- Skill Registry;
- versioning;
- lineage;
- provenance store;
- job orchestration;
- engine adapters;
- personal evidence store;
- trace curation;
- promotion / rollback;
- release state;
- Skill composition layer;
- UI/control plane.

This project should own the **control plane**, not reimplement every research algorithm.

---

## 11. Architectural principle: adapters, not a monolithic fork

Preferred repository structure:

```text
skill-factory/
├── apps/
│   ├── web/
│   └── api/
│
├── workers/
│   ├── distill/
│   ├── fuse/
│   ├── personalize/
│   ├── evaluate/
│   ├── curate/
│   └── evolve/
│
├── core/
│   ├── registry/
│   ├── lineage/
│   ├── provenance/
│   ├── releases/
│   ├── datasets/
│   └── curator/
│
├── adapters/
│   ├── arex/
│   ├── skillalchemy/
│   ├── skillcreator/
│   ├── phoenix/
│   ├── promptfoo/
│   └── trace2skill/
│
├── schemas/
│   ├── skill/
│   ├── job/
│   ├── source/
│   ├── evidence/
│   ├── trace/
│   └── eval/
│
└── packages/
    └── shared/
```

Do not copy all upstream source code into a single app.

Each engine adapter must expose a stable internal interface while upstream implementations can change.

---

## 12. Proposed implementation stack

This is a **local-first, single-user V1**.

Recommended stack:

### Web UI

- Next.js App Router
- TypeScript
- simple component library
- no complex design system required in V1

### Control/API

- FastAPI / Python
- reasons:
  - Trace2Skill is Python;
  - subprocess/worker orchestration is straightforward;
  - Phoenix Python ecosystem is mature;
  - easy integration with evaluation scripts.

### Persistence

- Supabase Postgres for metadata
- Supabase Storage for Skill packages / attachments / exported archives

### Job execution

V1:
- database-backed job queue;
- one local worker process;
- polling/claiming jobs;
- no Redis/Celery requirement.

V2:
- can move to a dedicated queue if concurrency requires it.

### Observability

- Phoenix as separate service/container.

### Engine execution

Engines are invoked through adapters using one of:

- CLI subprocess;
- local package/API;
- configured coding-agent CLI;
- HTTP endpoint where supported.

Each job gets an isolated workspace directory.

---

## 13. Canonical Skill identity

The registry, not the folder path, is authoritative.

Concept:

```text
skill_id = stable identity
skill_version_id = immutable version
release = pointer to a promoted version
```

Example:

```text
topic-selection
├── v1.0.0  archived
├── v1.1.0  production
├── v1.2.0  candidate
└── v1.0.3  rollback-capable
```

Never modify an immutable promoted version in place.

---

## 14. Skill lifecycle states

Recommended V1 states:

```text
draft
candidate
evaluating
passed
failed
production
archived
```

V2 may add:

```text
shadow
canary
deprecated
```

---

## 15. Source/evidence grades

For externally researched methodology:

```text
A = direct primary evidence / explicit statement / official implementation
B = repeated behavior or multiple independent strong sources
C = reasonable inference
D = speculation
```

Hard rules should normally require A/B evidence.

C may be represented as:

- scoped hypothesis;
- example;
- low-confidence note.

D should not become a reusable rule.

---

## 16. Licensing rule

The factory must preserve source licensing metadata where available.

This is especially important for repo-distilled Skills.

A generated Skill must not silently imply that all source code/content can be redistributed.

At minimum store:

- source URL;
- source repository;
- commit/ref if available;
- source license if detected;
- generated artifact license if explicitly known;
- redistribution warning/status.

---

## 17. V1 objective

V1 proves the following closed loop:

```text
Repo OR Unique Requirement
        ↓
AREX / SkillAlchemy
        ↓
Skill
        ↓
optional Fusion
        ↓
Personal Evidence
        ↓
Skill Creator Improve
        ↓
Eval Gate
        ↓
Version Registry
        ↓
Promote
        ↓
Export / Use
        ↓
Phoenix Trace Capture
```

V1 intentionally does **not** attempt autonomous self-improvement from production traces.

---

## 18. V2 objective

V2 adds:

```text
Production traces
    ↓
Outcome Attribution
    ↓
Trace Curator
    ↓
Trace2Skill generic evolution engine
    ↓
Candidate Skill
    ↓
Dev / Holdout / Regression / Generalization eval
    ↓
Promote / Reject / Rollback
```

V2 also adds upstream refresh and stronger layer composition.

---

## 19. Non-goals

V1 is **not**:

- a public SaaS;
- multi-tenant;
- a full multi-agent runtime;
- a marketplace for Skills;
- an automatic "clone any expert" system;
- a custom replacement for Phoenix;
- an autonomous system allowed to overwrite production Skills;
- a full GitHub mirror;
- a model training/fine-tuning platform.

---

## 20. Product principle

The strongest long-term asset is not any individual upstream engine.

The durable IP is:

```text
Skill schema
+ evidence
+ lineage
+ eval datasets
+ personal decisions
+ release history
+ curated production traces
```

AREX, SkillAlchemy, Skill Creator, Trace2Skill, or future alternatives should remain replaceable engines behind adapters.

---

## 21. Definition of success

The project succeeds when a user can answer all of the following for any production Skill:

1. What does this Skill do?
2. Which version is production?
3. Where did it come from?
4. Which parent Skills were fused?
5. Which sources support its major procedures?
6. Which personal corrections changed it?
7. Which eval dataset approved it?
8. Is it better than the previous production version?
9. Which production traces led to later changes?
10. Can we roll back safely?
11. Can upstream knowledge refresh without destroying the personal layer?
12. Can the Skill be exported as a normal portable Skill package?

If those answers are available, this is a Skill lifecycle system rather than a prompt folder.
