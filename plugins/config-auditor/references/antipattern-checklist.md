# Antipattern Checklist

Check every target against this list. Each item names the antipattern, why it
hurts, and the severity it usually carries. Severity can shift with context —
use judgment, but do not silently downgrade a security item.

## Trigger / description antipatterns

1. **Second-person or vague description** ("Use this to help with documents").
   Claude selects skills from the description alone; a vague one either
   undertriggering or fires on the wrong tasks. MAJOR.
2. **Missing WHEN / trigger phrases.** The description says what the skill does
   but never says when to reach for it. All "when to use" information belongs in
   the description, not the body. MAJOR.
3. **No exclusion clause where a sibling overlaps.** Two skills sharing keywords
   with no "do NOT use for…" boundary produce collisions; the wrong one fires.
   MAJOR, class `cross-scope-level` if it spans scopes.
4. **Key use case buried past ~250 characters.** A real listing truncation exists
   (GitHub issue #881), so the key use case should come first for HUMAN
   discoverability in the skill listing. Display-only: the model is given the
   full description for triggering (official docs), and the exact ~250 figure is a
   secondary-source estimate, not official. MINOR.
5. **Description over 1024 characters or containing XML tags.** BLOCKER (gate).
6. **Name not kebab-case, over 64 chars, or containing a reserved word**
   (`anthropic`/`claude`). Documented for **skills** → BLOCKER (gate); for
   **agents** these are convention → MAJOR. A **name≠directory** mismatch is a
   MAJOR convention issue, **not** a gate (the official example uses
   `pdf-processing` in a `pdf/` directory; Claude Code addresses a skill by its
   folder name, so a mismatch is confusing but not a load failure).
7. **Trigger information hidden in the body instead of the description.** The
   body loads only after the skill is already selected, so body-only triggers can
   never fire. MAJOR.

## Structure / maintainability antipatterns

8. **Everything in one oversized SKILL.md** (>500 lines, or a very large word
   count). Bloats context on every trigger and buries the signal. MAJOR.
9. **No progressive disclosure / unreferenced resources.** Bundled files that the
   SKILL.md never points to are dead weight; conversely, cramming reference-level
   detail into the body wastes context. MAJOR.
10. **Nested reference chains** (SKILL.md → A → B → C). Each hop costs a read and
    a chance to get lost. Prefer a flat references/ layout. MINOR–MAJOR.
11. **Phantom tools / TODO remnants.** The skill mentions a script it doesn't
    ship, or leaves placeholder text. Breaks execution. MAJOR.
12. **Body ↔ reference duplication.** The same content in two places drifts out
    of sync. MINOR.
13. **Duplicated target across global and repo scope** with diverging content.
    Which one wins is nondeterministic. MAJOR, class `cross-scope-level`.
14. **Hardcoded time-sensitive data** (prices, "latest version X", dated facts).
    Goes stale silently. MINOR–MAJOR.

## Security antipatterns

15. **No `allowed-tools` restriction.** The target inherits full tool surface it
    doesn't need. MAJOR (see security-checklist.md for the full treatment).
16. **Destructive Bash pattern in an allowed grant** without a narrowing
    guardrail. BLOCKER (gate).
17. **Plaintext secret in body or script.** BLOCKER (gate).
18. **Unnecessary secret / credential reads**, or references to environment
    variables that could exfiltrate. MAJOR.
19. **Prompt-injection surface**: hidden instructions in long bundled files,
    references to external domains, instructions to fetch-and-execute. MAJOR.

## Misclassification antipatterns

20. **Skill that should be a slash command / prompt** — situational, one-off,
    no reusable procedural knowledge. Noise in the model's skill list. MINOR.
21. **Destructive skill without `disable-model-invocation`** — a deploy/delete
    action that Claude can invoke on its own. MAJOR.
22. **Generic content with no novelty** — restates base-model knowledge. Adds
    context cost for no gain and can degrade performance. MAJOR modifier.

## Agent-specific antipatterns

23. **Contradictory or unscoped system prompt** — instructions that fight each
    other, or a role with no boundary. MAJOR.
24. **Tool mismatch** — the agent lacks a tool its stated job requires, or holds
    tools far beyond its role. MAJOR.
25. **Model misconfiguration** — judgment role on a weak model, or trivial role
    on the most expensive one. MAJOR (BLOCKER if unambiguous).
26. **No hand-back contract** — the agent never states how it returns results to
    the caller, so delegation output is unreliable. MAJOR.
27. **Delegation collision** — two agents with near-identical descriptions
    compete for the same task; selection becomes a coin flip. MAJOR, class
    `cross-scope-level`.
28. **Skill/agent coherence mismatch** — an embedded agent cannot deliver what
    its parent skill's description promises. MAJOR, class `coherence-level`.

## Coherence & honesty antipatterns

29. **Embedded agents that can't be spawned.** A skill bundles agents in an
    `agents/` subdirectory but is not a plugin (no `.claude-plugin/plugin.json`)
    and the agents are not also installed in `~/.claude/agents/`. Claude Code
    loads agents only from `~/.claude/agents/` (or a plugin), so a skill that
    instructs spawning its embedded agents has a **phantom capability**. MAJOR,
    class `coherence-level` (MINOR if the agents are demonstrably reference-only).
    Fix: move them to `~/.claude/agents/`, package the bundle as a plugin, or
    state plainly that they are reference-only.
30. **Name or description that oversells the behavior.** The name/description
    implies a capability the skill does not deliver as its default path — a
    "manager" that only reports, a "validator" that only lints. Erodes trust and
    mis-triggers. MAJOR.
31. **Unverified platform claim stated as fact.** The body or a comment asserts a
    specific Claude Code limit or behavior — a character cutoff, a truncation, a
    "the model won't see X" — as documented fact when it is an unverified
    heuristic. Verify it against the docs or label it a heuristic explicitly.
    MINOR–MAJOR.
32. **Reference content duplicated across sibling skills.** The same table or
    ruleset is copied into several skills that already share a conventions
    reference; the copies drift from each other and from the source of truth.
    MINOR, class `cross-scope-level`.
