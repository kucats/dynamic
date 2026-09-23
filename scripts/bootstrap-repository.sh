#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/bootstrap-repository.sh [OWNER/REPOSITORY] [--make-template]

When OWNER/REPOSITORY is omitted, the script resolves the current GitHub repository.
The optional --make-template flag marks the target itself as a template repository.
EOF
}

repo=""
make_template="false"

for arg in "$@"; do
  case "$arg" in
    --make-template)
      make_template="true"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -n "$repo" ]]; then
        echo "error: unexpected argument: $arg" >&2
        usage >&2
        exit 2
      fi
      repo="$arg"
      ;;
  esac
done

command -v gh >/dev/null 2>&1 || {
  echo "error: GitHub CLI (gh) is required" >&2
  exit 1
}

gh auth status >/dev/null

if [[ -z "$repo" ]]; then
  repo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
fi

if [[ ! "$repo" =~ ^[^/]+/[^/]+$ ]]; then
  echo "error: repository must be OWNER/REPOSITORY, got: $repo" >&2
  exit 2
fi

echo "Configuring $repo"

patch_args=(
  -F has_issues=true
  -F allow_squash_merge=true
  -F allow_merge_commit=false
  -F allow_rebase_merge=false
  -F delete_branch_on_merge=true
)

if [[ "$make_template" == "true" ]]; then
  patch_args+=(-F is_template=true)
fi

gh api --method PATCH "repos/$repo" "${patch_args[@]}" >/dev/null

# Auto-merge availability depends on repository and account settings. Keep failure non-fatal.
if ! gh api --method PATCH "repos/$repo" -F allow_auto_merge=true >/dev/null 2>&1; then
  echo "warning: auto-merge could not be enabled; review repository settings manually" >&2
fi

labels=(
  "priority:p0|b60205|Critical active impact, security/data risk, or release blocker"
  "priority:p1|d93f0b|Major functionality blocked or urgent"
  "priority:p2|fbca04|Normal planned priority"
  "priority:p3|c5def5|Minor, opportunistic, or polish"
  "status:blocked|000000|Cannot proceed until a named blocker is resolved"
  "status:needs-decision|5319e7|Requires an explicit design or product decision"
  "status:needs-validation|1d76db|Implementation exists but required evidence is incomplete"
  "agent:ready|0e8a16|Bounded and ready for a human or agent claim"
  "agent:claimed|0052cc|An identified worker owns the current attempt"
  "agent:human-required|b60205|A human-only approval or action is required"
  "type:design|d4c5f9|Architecture, protocol, or durable design decision"
  "type:handoff|bfdadc|Continuation record for incomplete work"
  "type:maintenance|ededed|Repository, dependency, tooling, or cleanup work"
)

for entry in "${labels[@]}"; do
  IFS='|' read -r name color description <<<"$entry"
  gh label create "$name" \
    --repo "$repo" \
    --color "$color" \
    --description "$description" \
    --force >/dev/null
done

cat <<EOF
Configured:
- Issues enabled
- squash merge enabled
- merge commits and rebase merge disabled
- automatic merged-branch deletion enabled
- standard agent/priority/status/type labels installed
$([[ "$make_template" == "true" ]] && echo "- repository marked as a template")

Review manually:
- main ruleset or branch protection
- required checks after CI job names exist
- Actions permissions and environments
- secrets and installed GitHub Apps
- CODEOWNERS and review requirements
- Copilot custom-instruction settings
EOF
