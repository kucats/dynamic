# Validation Contract

Replace the placeholders below with exact project commands before implementation begins.

## Required commands

| Scope | Command | Required environment | Expected result |
| --- | --- | --- | --- |
| Install/setup | `<COMMAND>` | `<ENVIRONMENT>` | `<RESULT>` |
| Format/lint | `<COMMAND>` | `<ENVIRONMENT>` | `<RESULT>` |
| Type/static check | `<COMMAND>` | `<ENVIRONMENT>` | `<RESULT>` |
| Unit tests | `<COMMAND>` | `<ENVIRONMENT>` | `<RESULT>` |
| Integration/contract tests | `<COMMAND>` | `<ENVIRONMENT>` | `<RESULT>` |
| Build/package | `<COMMAND>` | `<ENVIRONMENT>` | `<RESULT>` |
| Runtime smoke test | `<COMMAND_OR_PROCEDURE>` | `<ENVIRONMENT>` | `<RESULT>` |

Delete rows that genuinely do not apply; do not leave ambiguous placeholders in an active project.

## Validation strategy

During implementation, run the smallest relevant check frequently. Before review or merge, run every check required for the changed scope against the final head.

Behavior-sensitive changes may additionally require:

- failure-path and negative tests;
- migration forward/backward or compatibility checks;
- security and authorization boundary tests;
- browser, device, hardware, or operating-system evidence;
- screenshot or recording review;
- load, latency, memory, storage, or capacity measurements;
- deployment dry-run, canary, or rollback proof.

Static checks do not substitute for runtime evidence when the acceptance criterion is visual, interactive, distributed, hardware-specific, or operational.

## Evidence format

Record evidence in the pull request and active Issue:

```markdown
### Validation

- Commit: `<SHA>`
- Environment: `<OS/runtime/browser/hardware/region>`
- Command: `<exact command>`
- Result: `PASS|FAIL|BLOCKED`
- Output/artifact: `<sanitized excerpt or link>`
- Checks not run: `<none or exact reason>`
- Remaining risk: `<none or explanation>`
```

Do not claim `PASS` from an earlier head after code changes. Do not hide skipped checks. When infrastructure prevents a check, record the blocker, run the closest safe substitute, and leave the residual risk explicit.
