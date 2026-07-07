# Report Template

Use this exact structure for the Phase 1 audit report. It is written to be read
top-down: the summary gives the decision-maker the leverage points, the
scorecards give the detail, and the numbered recommendation list is the thing the
user approves from. Keep prose tight; this is a working document, not an essay.

Do not modify any target while producing this. The closing section must restate
that nothing was changed.

---

## Template

```markdown
# Skill, Agent & Plugin Audit — <date>

## Executive summary

Scanned <N> targets: <S> skills, <E> embedded agents, <A> standalone agents,
<P> plugins and <C> plugin surface components (hooks, monitors, MCP/LSP servers,
commands, settings), across <global count> global and <repo count> repo-local.

Grade distribution: 🟢 A ×_, 🟡 B ×_, 🟠 C ×_, 🔴 D ×_, ⚫ F ×_.
BLOCKERs outstanding: <count>.

Highest-leverage fixes (top 3–5 across the whole set):
1. <one line: target — the fix — the payoff>
2. …

## Grading table (MANDATORY — always produce this)

One row per target, worst grade first. Produce it on **every** run, even a fully
clean audit (all A's, zero findings) — it is the at-a-glance scoreboard, and the
per-target scorecards below simply expand each row. Never finish an audit without
this table.

The table carries **one Score per target — no per-dimension columns.** The dimension
breakdown lives in the per-target scorecard below; putting Trigger/Execution/etc. in
the summary turns the scoreboard into a wall of numbers. The single thing the summary
must still surface is whether a score is *measured* or *inspection-capped* — carried by
a compact marker on the Score, not a column.

**Color the Grade and Gate cells** with an emoji indicator (renders in the terminal, on
GitHub, and in artifacts — unlike ANSI or text color). Prefix the letter/word:

- Grade: 🟢 A · 🟡 B · 🟠 C · 🔴 D · ⚫ F
- Gate: ✅ PASS · ⛔ FAIL

| Target | Kind | Scope | Gate | Grade | Score | BLK | MAJ | MIN | Dism | Top finding |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| <name> | skill | repo | ✅ PASS | 🟢 A | 94‡ | 0 | 0 | 1 | 0 | <one-line top confirmed finding, or "—" if clean> |
| <name> | hook | repo | ⛔ FAIL | ⚫ F | 0 | 1 | 0 | 0 | 0 | fetch-and-execute in SessionStart hook |
| … | | | | | | | | | | |

BLK/MAJ/MIN count **CONFIRMED** findings only; **Dism** = raw script flags cleared on
adjudication (detailed per target below, never action items).

**Score marker — `‡` = inspection-capped.** Append `‡` to the Score when a
measurement-gated dimension contributing to the grade (Trigger, or Execution) is scored
by inspection at its 9 cap — i.e. the measurement was not run, so the score *could rise*.
A bare Score (no marker) means nothing is pending measurement: either every
measurement-gated dimension was actually measured, or the target is a kind with no
measured ceiling (config components: `hook`, `monitor`, `mcp_server`, `lsp_server`,
`plugin`, `settings`). A `plugin` row inherits `‡` when its worst child carries it. Add
one footnote line under the table: *"‡ inspection-capped — Trigger/Execution not
measured; see scorecard. Run `trigger_eval.py` to unlock."*

Kind is any of: `skill`, `standalone_agent`, `embedded_agent`, `command`, `plugin`,
`hook`, `monitor`, `mcp_server`, `lsp_server`, `settings`. **Group a plugin's rows
together:** the `plugin` container row first, then the rows for the components it
ships — the container's grade is the **worst** among them, so the grouping shows why.

## Per-target scorecards

### <target name> — Grade <🟢/🟡/🟠/🔴/⚫ letter> (score <0–100>) — <kind>, <scope>

Gate status: <✅ PASS | ⛔ FAIL: reason>
Dimensions:
- <dimension>: <0–10> — <one-line justification>
- …

Measured ceiling: <REQUIRED for skills/agents. Trigger and Execution cap at 9 by
inspection. State one: "Trigger/Execution capped at 9 (inspection) — run
`trigger_eval.py` to unlock 10 (~N `claude -p` calls, costs tokens); want me to?" |
"not measurable (disable-model-invocation / interactive)". **N/A for config-component
kinds** (hook, monitor, mcp_server, lsp_server, plugin, settings) — they are graded on
security posture, not trigger/execution, so a clean one earns a 10 by inspection.>

Findings (confirmed, severity-sorted):
- [BLOCKER·CONFIRMED] <finding> — why it matters — the change — <file>
- [MAJOR·CONFIRMED] …
- [MAJOR·PLAUSIBLE] <finding> — <what must be verified to confirm it> — <file>
- [MINOR·CONFIRMED] …

Adjudicated / dismissed flags (raw script flags cleared on inspection — NOT action items):
- [MAJOR·DISMISSED] <flag> — reason: not-applicable — <one line>
- [BLOCKER·DISMISSED] <flag> — reason: false-positive — <one line>
- (or "— none" when every raw flag was confirmed)

(repeat per target; order targets worst-grade-first so the user sees the
problems before the clean ones)

## Cross-cutting findings

Issues that span more than one target:
- [coherence-level] <skill> promises X but its embedded agent <agent> lacks the
  tools to deliver it.
- [plugin-level] <plugin> grades F because it ships <component> with a BLOCKER;
  the container inherits the worst component grade.
- [surface-level] <hook/monitor/server> in <plugin> <the executable/egress risk>.
- [cross-scope-level] <target> exists in both global and repo scope with
  diverging content; <which wins is nondeterministic>.
- [cross-scope-level] <agent A> and <agent B> have overlapping descriptions and
  compete for the same delegation.

## Prioritized recommendations

Ordered by leverage (severity × ease). **CONFIRMED and PLAUSIBLE findings only — a
DISMISSED flag is never a recommendation.** This is the list to approve from — reply
with the numbers you want applied.

1. <target>: <concrete change>. Why: <payoff>. File: <path>. Severity: <label>.
   Measurable: <if applicable, e.g. "run run_loop before/after to confirm
   trigger-rate gain">.
2. …

## Nothing has been changed

This was a read-only audit. No skill or agent was modified. Tell me which
numbered recommendations to apply and I'll hand off to the refactor phase
(skill-creator) to implement and measure them.
```

---

## Notes on filling it in

- **Order targets worst-first.** The user's attention is finite; spend it on the
  F's and D's before the A's.
- **Every finding needs the change, not just the problem.** "Description is
  vague" is not actionable; "rewrite the description to lead with the trigger
  phrases 'create a hook', 'add a PreToolUse hook'" is.
- **Attach measurability where a claim is empirical.** If a recommendation
  asserts better triggering or better output, name the eval that would prove it
  (run_loop for triggering, aggregate_benchmark for output). This keeps the
  report honest and sets up Phase 2.
- **Keep recommendations atomic.** One change per number so the user can approve
  a subset cleanly.
- **Do not renumber across runs silently.** If this is a re-audit, note which
  prior recommendations were applied and what changed.
- **The grading table is mandatory.** Produce it on every run, before the
  scorecards, even when every target is clean (all A's). "Grade everything and
  show it in a table" is the contract; a run that ends without the table is an
  incomplete audit.
- **Always state the measured ceiling.** Trigger and Execution cap at 9 by
  inspection; per target, either offer the measurement (`trigger_eval.py`, opt-in,
  costs tokens) to unlock 10, or say it is not measurable. Never silently score
  those two dimensions 9 — the reader must know a 9 is "pending measurement", not
  earned.
- **Every finding gets a verdict.** Severity is *how bad if real*; verdict is
  *whether it is real*. The grade and the recommendations count only CONFIRMED (and
  cautiously PLAUSIBLE). The dismissed block is transparency — it shows the scanner
  fired and why you overruled it — so a cleared flag is visible without masquerading
  as a to-do.
