# Bot Teams Roadmap

Last updated: 2026-03-26

This document records the current Bot Teams implementation status and the next planned milestones so the team can continue without losing context.

## Current stage

Bot Teams is at **MVP 1.0 + operational hardening**:

- Isolated bot workspaces/configs/memory/custom skills are supported.
- Team execution flows are available via CLI (`run`, `compare`, `dispatch`, `orchestrate`, `team run`).
- Static dashboard generation exists for quick visibility.
- Reliability safeguards were added for:
  - machine-readable JSON output behavior,
  - async config-path isolation,
  - corrupt registry recovery + backup.

## Milestone plan

## M1 (done) — Isolated Bot Runtime + Team CLI

Delivered:

- Bot/team registry and workspace scaffolding.
- Selector-based execution (`bot_id`, `tag`, `skill`, `query`).
- Multi-bot fanout, synthesis, quorum controls, JSON artifact output.
- Basic static dashboard and runtime summaries.

## M2 (next) — Routing Intelligence + Execution Policies

Goal: make orchestration more autonomous and safer by default.

Proposed scope:

1. **Auto-routing strategy presets**
   - Add pluggable strategies for selecting bots (`all`, `best_match`, `top_k`, `fallback_chain`).
   - Keep current manual selectors as an override.
2. **Execution policy profiles**
   - Named policy presets for timeout/concurrency/quorum/retry.
   - Team-level default policy + per-run override.
3. **Failure handling improvements**
   - Retry support for transient errors.
   - Optional fallback bot chain when synthesis quorum is not met.

Acceptance criteria:

- `nanobot bots orchestrate` can run with `--strategy` and `--policy`.
- Team-level default policy is persisted and respected by `team run`.
- Tests cover fallback and retry behavior.

## M3 — Observability API + Live Dashboard

Goal: move from static snapshots to live operational visibility.

Proposed scope:

1. Read-only HTTP API for bot/team/session/runtime summaries.
2. Event timeline for recent orchestration runs.
3. Live dashboard (polling first, streaming optional later).

Acceptance criteria:

- API endpoints expose bot/team/run summaries without mutating state.
- Dashboard can show run history, success/failure counts, and recent errors.

## M4 — Template Catalog + Governance

Goal: make bot creation standardized and production-friendly.

Proposed scope:

1. Role templates (e.g., thread-marketing, researcher, reviewer).
2. Budget/tool guardrails per bot/team.
3. Audit metadata for key bot/team changes.

Acceptance criteria:

- `bots create --template <name>` scaffolds predefined persona/memory/skills.
- Tool/budget constraints are enforceable during team runs.
- Audit trail is queryable.
