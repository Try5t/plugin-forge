---
name: concept-doc-standard
description: Binding documentation and evidence standard for every artifact of the concept phase. Defines storage location, file names, frontmatter, citation duty, and the return format to the Conductor.
user-invocable: false
allowed-tools: Read
---

# Documentation and Evidence Standard for the Concept Phase

This standard is binding for every expert. It ensures all artifacts are structured the same way and can later be aggregated across projects.

## Storage

All artifacts live under `docs/concept/` (relative to the Conductor's `<run-slug>` scope, i.e. `docs/concept/<run-slug>/` when a run slug is in use). Create directories yourself as needed. Write your artifact to disk yourself. Do not return it to the Conductor as prose — return only path, key points, and conflicts (see Return Format).

Fixed tree (all paths relative to `docs/concept/<run-slug>/`):

```
docs/concept/<run-slug>/
  00-brief.md                 conductor briefing (single source of truth)
  00b-assumptions.md          riskiest-assumption map + mini pre-mortem + scope/USP challenge (Phase A.5)
  05-scope-challenge.md       scope-and-value challenge — worth building? smallest version? (Phase A.5, only when activated)
  10-research.md              research, single file with sections: Market / Competition matrix / Standards / Prior-art / Anti-patterns
  20-ux-exploration.md        initial UX exploration — users, context, likely main flows (Phase B, assumptions only)
  30-product.md               product definition
  35-business.md              commercial viability — business model, unit economics, pricing, GTM, Go/No-Go (only when activated)
  40-ux-concept.md            UX concept
  45-data.md                  data / domain model      (only when activated)
  47-security.md              security + compliance     (only when activated)
  48-devops.md                devops / platform         (only when activated)
  50-architecture.md          architecture options + chosen approach
  adr/NNNN-<short-title>.md   one ADR per significant decision (MADR format), sibling of 50-architecture.md
  60-feasibility.md           feasibility
  70-qa.md                    quality + risk
  80-critique.md              red-team critique
  90-consolidated-concept.md  synthesis (canonical)
  95-retro.md                 process retro (canonical)
  README.md                   index, maintained by the Conductor
```

Numbers leave gaps on purpose (10/30/45/47/48/50/60/70/80/90) so conditional and ad-hoc artifacts (e.g. a mid-course `15-*` cross-check) slot in without renumbering. The retro is `95-` so it never collides with `10-research`.

## Frontmatter

Every artifact begins with this YAML block. It is the aggregation equivalent of page properties in Confluence.

```yaml
---
title: <plain title>
phase: <intake|research|product|ux|architecture|feasibility|quality|security|devops|data|challenge|synthesis>
role: <product-owner|researcher|architect|developer|qa|ux|critic|challenger|security|devops|data|orchestrator>
status: <draft|review|final>
date: <YYYY-MM-DD>
sources:
  - <source, or path to a research artifact, or "user input">
open_conflicts:
  - <conflict with another artifact, or empty>
---
```

## Citation Duty

Every decision-relevant statement must be traceable to one of the following sources:

- the research artifact `docs/concept/10-research.md`
- explicit user input from the intake
- a named standard or norm

Statements for which none of these sources exists are marked in the text with `[assumption, unverified]`. Mark too much rather than too little. A well-formatted guess without evidence is the most common failure of this phase.

**Do not inherit citations on trust.** When you rely on a code or fact claim made by a predecessor artifact, re-verify it at the source (open the `file:line`, re-read the standard) before building on it. A wrong claim that rides unchallenged from one phase into the next is how a phantom risk or a false "confirmed" reaches the critique — the second most common failure of this phase.

**For a code claim, verify invocation, not just existence.** Confirming a symbol *exists* (a class, method, or registration is present) is not the same as confirming it is *reached on a production path*. Before treating a component as "the live boundary" for anything, grep for its registration AND its call sites (who invokes it, is it wired into an agent/tool list/request path). A wired-but-unreachable seam — registered in DI but never called, or a value hardcoded past it — is a phantom: it will read as "verified" to every later phase while doing nothing. Existence is not invocation.

## Conflict Duty

Do not smooth over contradictions with other artifacts. Enter every conflict under `open_conflicts` and describe it in the text. Examples: the Product Owner's scope against the Architect's simplicity, QA's testability against the Developer's effort. The value of this phase lies in the unresolved conflicts, not in consensus.

## Return Format to the Conductor

At the end, return exactly this, concisely:

1. Path of the written artifact
2. Three to five key points
3. List of `open_conflicts`
4. List of `[assumption, unverified]` entries, if any

No long repetition of the artifact content. The Conductor reads the artifact itself when needed.
