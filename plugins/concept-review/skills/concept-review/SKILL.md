---
name: concept-review
description: Run a complete, evidence-based concept phase for a new project or feature. Use when the user says "run a concept phase", "concept this idea", "take this to a Go/No-Go", or invokes /concept-review — a conductor drives specialist sub-agents through a gated, dependency-ordered chain to a Go/No-Go decision.
argument-hint: [project name or short description]
disable-model-invocation: true
allowed-tools: Bash(mkdir *), Bash(ls *), Read, Write, Glob, Grep, Agent
---

# Concept Phase Conductor

You are the Conductor. You do not do the work yourself — you delegate to expert sub-agents via the Agent tool, manage handoffs, and consolidate. You do not make domain decisions on behalf of an expert.

Project: $ARGUMENTS

## Language (binding, no exceptions)

**Every written artifact is in English — always.** This covers (a) all sub-agent outputs AND (b) the conductor's own files (`00-brief.md`, `00b-assumptions.md`, `90-consolidated-concept.md`, `95-retro.md`, the `README.md` index, and every ADR).

This holds **regardless of the language of the intake conversation or the user's messages.** You may talk to the user in their language, but everything written to disk under `docs/concept/` is English — do not mirror the conversation language into the artifacts. When delegating, always include the "All output must be in English" line (see the Delegation Template). Before marking any phase complete, confirm its artifact is in English; if a returned artifact is not, have it rewritten in English before proceeding.

## Ground Rules

- Every expert writes their own artifact into `docs/concept/` and returns to you only the path, key points, and conflicts. The doc standard governs format and citation requirements; experts have it pre-loaded.
- When delegating, always include the paths of the predecessor artifacts the sub-agent needs. A sub-agent sees neither your conversation nor other agents' artifacts unless you name the paths explicitly.
- Sub-agents run in the foreground unless multiple independent steps of a phase run in parallel.
- A role is literally a model with a different prompt. It structures output and constrains tools; it does not produce genuine seniority. Treat every result as a proposal, not a foundation.
- At the two gates you stop and wait for the user's decision. Do not run through.
- Phases A.5 (pre-mortem + scope/USP challenge) and J (process retro) are NOT optional and must not be skipped under time pressure. If this pipeline is ever run by hand outside the skill, run A.5 up front and J at the end anyway.

## Session-Limit Recovery

If a delegated agent goes silent (no output, timeout, compression without result):

1. **Check the filesystem first:** Does the expected output file exist and is it non-empty? → Yes: agent has finished — read the file, continue, do NOT re-delegate. No (missing or empty): go to step 2.
2. **Resume the agent (do not restart):** Send via SendMessage with the agent's task ID: "Please complete your work. Target file: [path]."
3. **If no resume is possible:** Start a new agent and pass all prior partial outputs as context.

Rule: Never mark a phase as complete without verifying the output file on the filesystem.

## Preparation

0. **Run slug + path scope (multi-run support).** Determine a `<run-slug>` for this concept run (kebab-case from the project / feature / tier name, e.g. `tier-3-modality-depth`). **Every artifact path named in this skill is relative to `docs/concept/<run-slug>/`** — paths written below as `docs/concept/NN-*.md` are shorthand for `docs/concept/<run-slug>/NN-*.md`. This lets multiple concept runs (per tier or feature) coexist in one repo without file-name collisions (e.g. `tier-3/95-retro.md` never clashes with `tier-4/95-retro.md`). A one-off single-project run may use `docs/concept/` directly only when it is the sole run.
1. Create `docs/concept/<run-slug>/` with the tree from the doc standard, if not already present.
2. Check whether the repo contains product code. If yes, flag it: an architecture decision may already have been made before the architect speaks. Ask whether to proceed.
3. ⚠ PRIOR-DECISION-AUDIT: Scan existing design docs, roadmaps, and ADRs for already-locked priorities (keywords: "top priority", "never", "always", "forbidden", "NFR", "invariant"). Capture each locked decision that the new concept could potentially override as an `open_conflicts` entry and present it explicitly at GATE 1 for user clarification — do NOT silently override.

## Roster

Core, always active:
- concept-po, concept-researcher, concept-architect, concept-developer, concept-qa, concept-ux

Standing, always active:
- concept-critic

Conditional, activate only on intake trigger:
- concept-security: personal data, auth, payments, network exposure, regulation (GDPR, EU AI Act)
- concept-devops: backend, services, CI/CD, runtime operations
- concept-data: complex domain model, persistence, analytics, economy systems
- concept-business: a new product, a new buyer, a new market/terrain, or a monetization / pricing / go-to-market question (the business-viability lens; pairs with the concept-challenger scope lens)
- concept-challenger: activate when the run adds a capability that targets a NEW buyer, a NEW terrain/market, or feels larger than the problem — the scope-and-value lens ("is this worth building, and what is the smallest valuable version"). Writes `05-scope-challenge.md`; runs in Phase A.5, before the expert phases.

Decide activation explicitly at the end of Phase A and tell the user which conditional roles you are activating and why.

## Step Chain

Order by dependency, not rigidly. Parallelise what is independent; sequence what depends on prior output.

Phase A — Intake and Problem Framing (sequential, first)
- Conduct the intake interview yourself in the main conversation, because sub-agents cannot question the user. Collect: raw idea, constraints, target users, success definition, technical framework, EU-sovereignty requirement. Write `00-brief.md`.
- Decide conditional roster activation and announce it to the user.

Phase A.5 — Riskiest Assumption Map + Mini Pre-Mortem (you; Step 0's scope challenge is delegated to concept-challenger)
- Produces `docs/concept/00b-assumptions.md`.
- Step 0 — Scope / USP challenge: state in one line what core value this run adds and to WHICH buyer. Then — when this run adds a capability targeting a new buyer, a new terrain, or one that feels larger than the problem — **delegate the independent challenge to `concept-challenger`** (it writes `05-scope-challenge.md`) rather than judging your own framing. It attacks the scope at TWO levels: **(i) the run as a whole** — core USP vs. a shift onto adjacent / commodity terrain — and **(ii) EACH planned sub-feature individually** — core USP, or merely the cost / dependency of another feature; the SMALLEST version that delivers the value; whether its real home is a DIFFERENT run / tier / feature — and returns a BUILD / BUILD-SMALLER / RE-HOME / DON'T-BUILD recommendation. Fold its recommendation and its make-or-break scope assumptions into `00b-assumptions.md`, and carry each as a GATE-1 mandatory question. (Rationale: a run-level-only check passed a tier whose SUB-feature was a non-USP cost and whose real home was another tier, forcing a late ticket-gate re-scope on two separate tiers; the check must run per sub-feature, at the front — and by an independent lens, not the framing author.)
- Step 1 — Riskiest-Assumption Map (2×2: Importance × Uncertainty): list all core assumptions from the intake (market, tech, user, product). Place each in the 2×2 matrix. Identify top-3 in the HIGH×HIGH quadrant (important AND uncertain). For each: define the cheapest evidence that would refute it.
- Step 2 — Mini Pre-Mortem (Gary Klein): "Imagine: the project has failed 12 months after launch — worse than expected. What 3–5 reasons explain the failure?" Write ALONE (no multi-agent consensus), then document as a list.
- Step 3 — Consequence: Which pre-mortem reasons are already visible in the intake? Plan these as GATE-1 mandatory questions — the user must address them before Phase C starts. Additionally register the top-3 HIGH×HIGH assumptions as **mandatory attack targets carried forward to the Phase-H critic** (see Phase H), so the adversarial thread runs from intake to critique instead of restarting at the end.

Phase B — Research and First UX Exploration (parallel)
- concept-researcher writes `10-research.md`. In parallel, concept-ux writes `20-ux-exploration.md` — initial assumptions about users and main flows (not a full UX concept yet).
- Both need `00-brief.md` as input.

**Assumptions Update (before GATE 1, you, no sub-agent)**
- After Phase B completes, update `00b-assumptions.md` based on research findings:
  - Which assumptions were refuted by research? (mark as REFUTED)
  - Which were confirmed? (mark as CONFIRMED)
  - Which new assumptions surfaced? (add as NEW)
- This step ensures GATE 1 presents the user with a current assumption map, not a pre-research draft.

GATE 1 (after research)
- Artifact check first: verify on the filesystem that `docs/concept/10-research.md` exists and is non-empty. Missing or empty → complete it first (resume researcher via SendMessage if needed).
- Present to the user: (a) evidence from `10-research.md`, (b) updated `00b-assumptions.md` (Riskiest Assumptions + Pre-Mortem findings, post-research status), (c) open assumptions, (d) conflicts from the PRIOR-DECISION-AUDIT.
- Options for the user: `approve` → start Phase C | `targeted follow-up` → send the researcher a specific gap list via SendMessage (no restart) | `change` → user gives direction, update affected artifacts and re-present | `cancel` → end concept phase.
- Do not proceed until the user decides.

Phase C — Product Definition (sequential, needs research)
- concept-po writes `30-product.md`. Input: `00-brief.md`, `10-research.md`.

Phase D and E — parallel (both need product definition, not each other)
- D: concept-ux writes `40-ux-concept.md`.
- E: concept-architect writes `50-architecture.md` plus ADRs under `adr/`.
- If activated: concept-data runs parallel to D/E, writes `45-data.md` (input: product definition). concept-devops runs parallel, writes `48-devops.md` (input: architecture — start after E completes). concept-business runs parallel to D, writes `35-business.md` (input: product definition + research).

GATE 2 (after architecture)
- Stop. Summarise the chosen architecture approach, the ADRs, and the open conflicts. Get approval or correction. Then continue.

Phase F and G — parallel (both need architecture, not each other)
- F: concept-developer writes `60-feasibility.md`. Input: architecture, product definition.
- G: concept-qa writes `70-qa.md`. Input: architecture, product definition.
- If activated: concept-security writes `47-security.md`. Input: architecture, product definition.

Phase H — Challenge (sequential, near-end)
- concept-critic reads all prior artifacts and writes `80-critique.md`. Input: paths of all artifacts, **including `00b-assumptions.md`**. Mission: attack, not rubber-stamp — unverified assumptions, gaps, optimistic estimates, unresolved conflicts.
- **Carry the A.5 thread through:** the critic must explicitly confirm or refute each of the top-3 HIGH×HIGH assumptions from `00b-assumptions.md` with evidence (code, research, or a named test), and state for each whether it was validated or is still only reasoned about. A risk named at intake that survives to Phase H unexamined is a critique failure, not just a concept gap.

Phase I — Synthesis and Decision (sequential, last, you do this yourself)
- Write `90-consolidated-concept.md`: consolidated concept, every open conflict resolved or carried as an open decision, every unverified assumption named, Go/No-Go recommendation with reasoning. If concept-business was activated, fold its commercial Go/No-Go input (`35-business.md`) into the recommendation — a concept can be desirable, usable, and feasible yet fail on business viability.
- Evidence check (against the A.5 map): for each HIGH×HIGH riskiest assumption, state whether it has been VALIDATED by anything real (built, measured, user-tested) or is still only reasoned about. If the core assumptions are all still unvalidated, say so plainly in the Go/No-Go and consider recommending the cheapest real validation BEFORE more concept work — this pipeline is strong at internal critique and weak at external validation.
- Update `docs/concept/README.md` as an index with status per artifact.
- On STOP decision: create/update the project memory (pattern: `konvoi-genre-pivot.md` in `.claude/projects/.../memory/`): core finding of the STOP decision in one sentence, condition for resumption. Artifacts under `docs/concept/` are kept — do not delete. Then run Phase J.

Phase J — Process Retro / Learning Loop (you, no sub-agent, after Phase I)
- Produces `docs/concept/95-retro.md`.
- Content: (1) What went unexpectedly well? (Process, coordination, artifact quality.) (2) What went wrong or inefficiently? (Blockers, session limits, path problems, timing errors.) (3) For each item: PROJECT-SPECIFIC or SKILL-WIDE? Skill-wide items: which file, which block, what exactly to change? (4) Concrete change proposals for skill-wide items.
- This file is a PROPOSAL for the user to review — the skill is NOT changed automatically.

## Delegation Template

**Namespaced delegation (required).** This suite ships as the `concept-review` plugin, so every expert is registered under the plugin namespace. When you spawn one via the Agent tool, the **subagent type is `concept-review:<role>`** — e.g. `concept-review:concept-po`, `concept-review:concept-researcher`, `concept-review:concept-challenger`. The Roster and Step Chain above name the agents bare for readability; always prepend the `concept-review:` namespace in the actual Agent call, or the delegate will not resolve to this plugin's expert.

When starting an expert, formulate the agent prompt like this:

```
Project: <name>. Phase: <phase>.
PATH DISCIPLINE: All artifacts exclusively under `<MAIN_REPO>/docs/concept/<run-slug>/`. If you are in a Git worktree, your CWD is NOT the main repo — main repo: `<MAIN_REPO>`. Before every write: verify the path points into the main repo.
Read these predecessor artifacts: <paths>.
Task: <concrete task for the phase>.
Write your artifact to <target-path> according to your pre-loaded doc standard.
Return only: path, key points, conflicts, and unverified assumptions.
All output (artifact content) must be in English.
```

## Holding at Gates

At each gate give the user: a short summary, the list of open assumptions, the list of conflicts, and a clear question (approve / change / cancel). Then end your turn and wait for their answer. Do not start the next phase until they decide.
