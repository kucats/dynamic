# Agent-Friendly Repository Template

A repository baseline for projects developed by humans and coding agents through GitHub Issues and pull requests.

The template is intentionally language- and framework-neutral. It provides the operating contract, work-tracking structure, and evidence standards; each generated repository must add its own architecture, commands, and domain constraints.

## Start a new repository

1. Select **Use this template** on GitHub and create the repository from the default branch.
2. Complete [`TEMPLATE_SETUP.md`](TEMPLATE_SETUP.md).
3. Run `./scripts/bootstrap-repository.sh OWNER/REPOSITORY` after authenticating GitHub CLI.
4. Replace the project placeholders in [`AGENTS.md`](AGENTS.md), [`docs/architecture/README.md`](docs/architecture/README.md), and [`docs/testing.md`](docs/testing.md).
5. Create the first Issue before implementation begins.

GitHub template repositories copy directory structure and files. Repository settings, labels, rulesets, secrets, environments, installed apps, and existing Issues or pull requests require separate setup. The bootstrap script applies a conservative baseline for merge settings and labels; review repository rules manually for the project's risk level.

## Included operating model

```text
Issue intake
  -> acceptance criteria and boundaries
  -> agent claim with identity and scope
  -> branch or explicitly authorized direct-main change
  -> implementation with progress updates
  -> validation evidence
  -> pull request and review
  -> squash merge
  -> Issue completion record
  -> merged branch cleanup
```

The templates enforce several recurring rules:

- Work is coordinated through Issues; do not silently start overlapping work.
- An agent declares its identity, scope, base commit, and branch before changing files.
- One Issue should represent one reviewable outcome.
- Validation evidence names exact commands, environments, and results.
- Blocked or incomplete work is handed off with exact refs and remaining steps, never reported as complete.
- Merge is permitted only when acceptance criteria, checks, review state, and authorization are satisfied.
- Merged branches are removed to keep the base clean.
- Destructive operations, production changes, secret handling, spending, and other high-risk actions require explicit human authorization.

## Repository map

| Path | Purpose |
| --- | --- |
| `AGENTS.md` | Short, authoritative map and agent operating rules |
| `AGENT.md` | Compatibility pointer to `AGENTS.md` |
| `.github/copilot-instructions.md` | Concise GitHub Copilot repository instructions |
| `.github/ISSUE_TEMPLATE/` | Structured work, bug, design, and handoff intake |
| `.github/PULL_REQUEST_TEMPLATE.md` | Review and evidence contract |
| `docs/repository-contract.md` | Instruction hierarchy and sources of truth |
| `docs/issue-management.md` | Issue state machine, claim comments, progress, and closure |
| `docs/testing.md` | Project validation matrix and evidence format |
| `docs/exec-plans/` | Living plans for multi-step or high-risk work |
| `docs/decisions/` | Architecture Decision Records |
| `docs/handoffs/` | Exact continuation records for unfinished work |
| `scripts/bootstrap-repository.sh` | Optional labels and merge-setting bootstrap |

## Maintenance model

Keep `AGENTS.md` compact. It should be a map, not an encyclopedia. Put durable design facts in `docs/`, executable validation in scripts or CI, and task-specific facts in Issues and pull requests.

Changes made later to this template do not automatically propagate into repositories previously generated from it. Record the originating [`TEMPLATE_VERSION`](TEMPLATE_VERSION), then port material template improvements through a normal Issue and pull request in each child repository.
