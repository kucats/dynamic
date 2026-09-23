# Repository Contract

## Purpose

This repository treats durable documentation, executable checks, and GitHub work records as a shared control plane for humans and agents.

The root `AGENTS.md` is a concise map. It must not become a full project encyclopedia. Detailed facts belong in stable sources of truth:

| Information | Source of truth |
| --- | --- |
| Purpose, global rules, navigation | root `AGENTS.md` |
| Component-local rules | nearest nested `AGENTS.md` |
| System structure and invariants | `docs/architecture/` |
| Material accepted choices | `docs/decisions/` |
| Multi-step implementation state | `docs/exec-plans/` |
| Required checks and environments | `docs/testing.md` and executable scripts |
| Task scope and acceptance | GitHub Issue |
| Proposed code and final evidence | pull request |
| Unfinished continuation state | Issue plus `docs/handoffs/` |
| Actual behavior | source code, schemas, tests, and deployed configuration |

## Instruction hygiene

- Avoid copying the same rule into multiple instruction files.
- Prefer a link to an authoritative document over a long inline explanation.
- Give every durable rule a clear scope and owner.
- Update documentation in the same change that invalidates it.
- Remove stale instructions instead of preserving contradictory history in active files.
- Use nested `AGENTS.md` only for genuinely local rules; the nearest file takes precedence for its subtree.
- Surface conflicts explicitly in the active Issue before implementation continues.

## Authorization boundary

An Issue can authorize ordinary repository-local, reversible work within its stated scope when repository policy allows it.

An Issue alone does not authorize:

- production deployment or live-data mutation;
- destructive deletion or irreversible migration;
- secret access, rotation, revocation, or disclosure;
- external communication, purchases, or legal commitments;
- broadening a security, protocol, API, or compatibility contract;
- bypassing required review, tests, signing, or audit controls.

Those actions require explicit human authorization and, where appropriate, protected environments or approval gates.

## Template customization

A generated repository is not ready until `TEMPLATE_SETUP.md` is completed. Replace placeholders, define real validation commands, document architecture and stop boundaries, and configure GitHub metadata.

Do not leave generic template text pretending to be project-specific truth.
