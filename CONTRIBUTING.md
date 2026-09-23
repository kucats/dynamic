# Contributing

## Issue first

Open or identify an Issue before making a non-trivial change. Search existing Issues and handoffs first; update the existing record rather than duplicating it.

An actionable Issue states:

- the problem or opportunity;
- the intended outcome;
- in-scope and out-of-scope work;
- acceptance criteria;
- constraints and human-only boundaries;
- validation and evidence expectations;
- dependencies or related work.

Small typo-only changes may skip a dedicated Issue when repository policy permits it.

## Claim and coordinate

Before implementation, post a claim in the Issue using the format in `docs/issue-management.md`. The claim prevents overlapping agents from silently editing the same area.

Respect explicit work allocation such as repository, subsystem, or odd/even Issue shards. Do not take work outside the assigned shard.

## Branch and pull request

Use `agent/issue-<number>-<short-slug>` unless a human contributor convention is documented.

A pull request must:

- link the tracking Issue, using `Closes #<number>` only when it fully resolves it;
- describe scope and non-goals;
- identify risk and rollback;
- include exact validation evidence;
- disclose skipped checks or unresolved limitations;
- update relevant documentation;
- remain draft while known merge blockers exist.

## Review and merge

Address review feedback on the current head and rerun affected checks. Do not resolve a thread without either applying the fix or explaining why no change is needed.

Squash merge is the default. Delete the branch after merge. Close the Issue only after its acceptance criteria are met and the final Issue comment records the merge commit, validation, and remaining follow-up.

## Security

Do not report vulnerabilities or credentials in public Issues. Follow `SECURITY.md`.
