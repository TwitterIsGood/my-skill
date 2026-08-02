---
name: reverse-skill
description: Route authorized reverse engineering, CTF, malware analysis, mobile security, firmware, forensics, and penetration-testing work through the bundled reverse-skill suite. Use when a security task needs one of the suite's specialist workflows or its master router.
---

# Reverse Skill Suite

Use the pinned, complete snapshot of
[`zhaoxuya520/reverse-skill`](https://github.com/zhaoxuya520/reverse-skill)
under `upstream/`. Keep the snapshot intact because its specialist skills depend
on shared routing, operations contracts, scripts, and the CTF sandbox
orchestrator.

Limit use to targets the user owns or is authorized to test. Prefer
offline inspection and non-destructive triage until scope and authorization are
clear.

## Entry Point

1. Read [`upstream/RULES.md`](upstream/RULES.md).
2. Read [`upstream/skills/SKILL.md`](upstream/skills/SKILL.md).
3. Resolve all paths in those files relative to `upstream/` and follow the
   selected specialist workflow.

Do not copy an individual nested skill out of `upstream/`; that breaks its
relative references and shared workflow contracts.
