---
name: embedded-agents
description: Fixture for the embedded-agent invocability check. Use when the auditor must flag a skill that spawns bundled agents but is not a plugin, so the agents are not actually invocable as subagents.
---

# embedded-agents

This skill delegates the real work to a bundled worker subagent: it spawns the
`worker` agent from its own `agents/` folder. Because this fixture is not packaged
as a plugin, that worker is a phantom capability the auditor should catch.
