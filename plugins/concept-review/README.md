# Concept Review

An evidence-based **concept-phase pipeline** for a new project or feature. A Conductor
skill drives a roster of specialist sub-agents through a gated, dependency-ordered chain
— intake → research → product → UX → architecture → feasibility → QA → red-team critique
→ synthesis — and stops at two human gates on the way to a **Go/No-Go** decision.

## Components

| Component | Role |
|---|---|
| `concept-review` (skill) | The Conductor — delegates, manages hand-offs, holds the gates, writes the synthesis. Invoked as `/concept-review` (or `concept-review:concept-review`). |
| `concept-doc-standard` (skill) | The binding documentation + evidence standard every artifact follows. Loaded by each agent via its `skills:` dependency. |
| 12 `concept-*` agents | Specialists: `po`, `researcher`, `architect`, `developer`, `qa`, `ux`, `critic` (red team), `challenger` (scope/value), plus the conditional `security`, `devops`, `data`, `business`. Namespaced as `concept-review:concept-<role>`. |

## Install

```bash
claude plugin marketplace add https://gitlab.com/Try5t/plugin-forge.git
claude plugin install concept-review@plugin-forge
```
Restart the session (or `/reload-plugins`), then run `/concept-review <project or feature>`.

## How it works

Every expert writes its own artifact into `docs/concept/<run-slug>/` (numbered per the
doc standard), returns only path + key points + conflicts, and the Conductor consolidates.
Two gates (after research, after architecture) stop for a human decision. Assumptions and
conflicts are carried explicitly from intake to critique; nothing is smoothed over.

## Conventions

- **Every artifact is in English**, regardless of the conversation language.
- Each decision-relevant statement is cited (research / user input / named standard) or
  marked `[assumption, unverified]`.
- Conflicts between artifacts are recorded under `open_conflicts`, not resolved by fiat.

See `skills/concept-doc-standard/SKILL.md` for the full documentation and evidence standard.
