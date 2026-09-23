# Issue Management for Humans and Agents

## State model

Use comments and labels to represent this lifecycle:

1. **Intake** — problem exists, but scope or evidence may be incomplete.
2. **Ready** — outcome, boundaries, acceptance criteria, and validation are actionable.
3. **Claimed** — one identified worker owns the current attempt.
4. **In progress** — implementation is active on a named branch or authorized direct-main change.
5. **Review** — implementation is complete enough for pull-request review; evidence is attached.
6. **Blocked** — a specific dependency, decision, environment, or human action prevents progress.
7. **Done** — accepted change is merged, evidence is recorded, residual work is split, and branch cleanup is complete.

Do not close an Issue merely because code was written. Close only when its acceptance criteria are satisfied.

## Issue quality

Prefer one observable outcome per Issue. An Issue should answer:

- Why does this matter now?
- What end state must be observable?
- What is included and excluded?
- What constraints may not change?
- How will completion be proven?
- Which actions require a human?
- What existing Issue, decision, branch, or pull request is related?

Split unrelated or independently mergeable work. Use a parent tracking Issue only when several child Issues form one initiative.

## Agent claim comment

Post this before changing files:

```markdown
## Agent claim

- **Agent:** `<tool-or-agent>/<stable-short-id>`
- **Scope:** Issue #<number> only
- **Outcome:** <one sentence>
- **Base:** `<commit SHA>`
- **Branch:** `agent/issue-<number>-<slug>` or `direct main authorized by <who>`
- **Areas:** `<files, components, or repositories>`
- **Dependencies:** `<Issues, PRs, decisions, environments>`
- **Stop boundaries:** `<human-only or prohibited actions>`
- **Started:** `<ISO-8601 timestamp>`
```

If another active claim overlaps, coordinate in the Issue instead of racing. Respect explicit sharding such as odd/even Issue allocation.

## Progress comments

Comment only at material checkpoints, not after every command. Recommended checkpoints:

- plan and acceptance criteria confirmed;
- implementation complete;
- validation complete with exact results;
- blocker or unexpected design conflict found;
- scope changed or follow-up Issue created;
- pull request opened or merged.

A progress comment should identify the current head and distinguish completed, pending, and unverified work.

## Completion comment

After merge:

```markdown
## Completion

- **Merged PR:** #<number>
- **Merge commit:** `<SHA>`
- **Delivered:** <observable outcome>
- **Validation:** <commands/environments/results>
- **Acceptance criteria:** complete
- **Residual work:** none, or links to newly scoped Issues
- **Cleanup:** merged branch deleted
```

Close the Issue only after posting this record. If GitHub auto-closes it through `Closes #`, add the completion record immediately afterward.

## Direct-to-main exception

Direct commits are acceptable only when explicitly authorized by the owner or repository policy. The worker still must:

- use or create a tracking Issue;
- post a claim before writing;
- work from current `main`;
- keep the change atomic and scoped;
- validate the final commit;
- post the commit and evidence;
- close only after acceptance criteria are met.

## Blocked work and handoff

When work cannot be finished:

- update the active Issue and pull request before stopping;
- create or update a single handoff record;
- provide exact base/head SHAs, branch, PR, commands, results, artifacts, blockers, and next safe action;
- identify stale artifacts and forbidden shortcuts;
- keep the Issue open unless the work is explicitly cancelled or superseded.

Never use confident completion language for unmerged, unvalidated, or partial work.

## Suggested labels

The bootstrap script creates a compact label set:

- `priority:p0` through `priority:p3`
- `status:blocked`
- `status:needs-decision`
- `status:needs-validation`
- `agent:ready`
- `agent:claimed`
- `agent:human-required`
- `type:design`
- `type:handoff`
- `type:maintenance`

Labels aid filtering; the Issue body and comments remain the authoritative state record.
