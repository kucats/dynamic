# Template Setup Checklist

Complete this checklist in every repository generated from this template. Delete this file when setup is complete, or retain it as an audited setup record.

## Identity and scope

- [ ] Replace the README title and description.
- [ ] Record the repository purpose and non-goals in `AGENTS.md`.
- [ ] Add the real architecture map to `docs/architecture/README.md`.
- [ ] Remove template files that are not relevant to the project.
- [ ] Choose and add an explicit license, or document that the repository is proprietary.

## Development contract

- [ ] Add exact install, build, lint, type-check, test, and local-run commands to `docs/testing.md`.
- [ ] Add stack-specific conventions in a nested `AGENTS.md` near the relevant code.
- [ ] Define generated files, vendored code, migrations, and files agents must not edit manually.
- [ ] Define production, deployment, data, and secret-management stop boundaries.
- [ ] Add `.env.example` or equivalent with names only; never commit secrets.

## GitHub configuration

- [ ] Run `./scripts/bootstrap-repository.sh OWNER/REPOSITORY`.
- [ ] Confirm Issues are enabled.
- [ ] Confirm squash merge is enabled and merged branches are deleted automatically.
- [ ] Choose a `main` ruleset or branch-protection policy appropriate to the project.
- [ ] Configure required status checks after CI job names exist.
- [ ] Configure CODEOWNERS or reviewers where review independence is required.
- [ ] Configure Actions permissions, environments, secrets, and deployment approvals.
- [ ] Confirm GitHub Copilot custom instructions are enabled where used.

## First tracked work

- [ ] Create an Issue that defines the initial implementation outcome.
- [ ] Post an agent or human claim before implementation.
- [ ] Use a branch and pull request unless direct-to-main work is explicitly authorized.
- [ ] Record validation evidence and close the Issue only after acceptance criteria are met.
