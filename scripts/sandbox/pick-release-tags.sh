#!/usr/bin/env bash
# Pick the release tags the install/update E2E should update FROM.
#
# Emits a JSON array of tag names on stdout, suitable for a GitHub Actions
# matrix (`fromJSON`). Choosing at runtime rather than hardcoding keeps the
# matrix honest as releases land: a pinned list silently stops covering the
# newest release the day after it ships, and pins an "oldest" forever even
# after it stops being a version anyone still runs.
#
# Selection: the newest tag, the oldest tag, and evenly spaced tags in between.
# Newest catches "did the last release break updating?", oldest is the longest
# upgrade jump anyone can still make, and the spread samples the migrations in
# between (config-schema bumps, venv layout changes, dependency floors).
#
# Usage:
#   scripts/sandbox/pick-release-tags.sh [--count N] [--repo DIR] [--remote REMOTE]
#
#   --count   how many tags to emit (default 5, minimum 1). Fewer tags than
#             requested emits all of them.
#   --repo    repository whose origin to read tags from (default: this
#             checkout).
#   --remote  release remote name or URL (default: origin). Fork CI can name
#             the canonical upstream without mirroring its tag refs.
#
# Tags come from origin via ls-remote, so a checkout with no local tags works.
# Only the picked tags are materialized as local refs -- never the
# canary and backup refs a full --tags fetch would pull -- because the caller
# walks the picked tags' trees, which needs their refs present. Exits non-zero
# when origin has no release tags rather than silently emitting an empty
# matrix.
# All release candidate objects are fetched without tag refs for ancestry
# verification; only ancestors of HEAD may be selected (no fork downgrade).
# Full history is required; divergent local selected tags are not overwritten.
#
# Only vYYYY.M.D[.N] release tags are considered; the repo also carries
# backup/* and one-off tags that are not releases.

set -euo pipefail

COUNT=5
REMOTE=origin
# Default to the repository containing this script, resolved through its real
# path so a symlinked or copied script still reads the checkout it lives in
# rather than whatever repo the caller happens to be standing in.
REPO=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --count)
      [ "$#" -ge 2 ] || { echo 'error: --count needs a value' >&2; exit 1; }
      COUNT="$2"; shift 2 ;;
    --repo)
      [ "$#" -ge 2 ] || { echo 'error: --repo needs a value' >&2; exit 1; }
      REPO="$2"; shift 2 ;;
    --remote)
      [ "$#" -ge 2 ] && [ -n "$2" ] && [[ "$2" != -* ]] || { echo 'error: --remote needs a remote name or URL' >&2; exit 1; }
      REMOTE="$2"; shift 2 ;;
    -h|--help) sed -n '2,31p' "$0"; exit 0 ;;
    *) echo "error: unknown argument: $1" >&2; exit 1 ;;
  esac
done
case "$COUNT" in
  ''|*[!0-9]*) echo "error: --count must be a positive integer: $COUNT" >&2; exit 1 ;;
esac
[ "$COUNT" -ge 1 ] || { echo "error: --count must be at least 1" >&2; exit 1; }

# Resolve the script's own location through symlinks, then ask git which
# worktree that path belongs to. Deriving the repo from the script rather than
# from $PWD means a copied script cannot silently report a different checkout's
# tags, and --show-toplevel keeps it correct when invoked from a subdirectory.
if [ -z "$REPO" ]; then
  script_path="${BASH_SOURCE[0]}"
  if command -v readlink >/dev/null 2>&1; then
    script_path="$(readlink -f "$script_path" 2>/dev/null || printf '%s' "$script_path")"
  fi
  script_dir="$(cd "$(dirname "$script_path")" && pwd)"
  REPO="$(git -C "$script_dir" rev-parse --show-toplevel 2>/dev/null || printf '%s' "$script_dir")"
fi

# A shallow graph cannot prove that an older release is absent from HEAD.
# Fail closed rather than silently selecting an incomplete upgrade matrix.
if [ "$(git -C "$REPO" rev-parse --is-shallow-repository)" = true ]; then
  echo 'error: shallow history cannot prove release ancestry; fetch full history first' >&2
  exit 1
fi

# Discover names AND object IDs from origin; local tag refs are not trusted.
remote_tags="$(git -C "$REPO" ls-remote --refs --tags "$REMOTE" 'v*')"
declare -A release_oid=()
while read -r oid ref; do
  tag="${ref#refs/tags/}"
  if [[ "$tag" =~ ^v[0-9]{4}\.[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
    release_oid["$tag"]="$oid"
  fi
done <<<"$remote_tags"
mapfile -t candidates < <(
  for tag in "${!release_oid[@]}"; do printf '%s\n' "$tag"; done | sort -V
)
if [ "${#candidates[@]}" -eq 0 ]; then
  echo 'error: no vYYYY.M.D[.N] release tags found on origin' >&2
  exit 1
fi

tags=()
for tag in "${candidates[@]}"; do
  oid="${release_oid[$tag]}"
  # Fetch objects only, without creating unselected refs. Peeling handles
  # annotated tags; use the advertised snapshot, not a possibly stale local ref.
  git -C "$REPO" fetch --quiet --no-tags --no-write-fetch-head "$REMOTE" "$oid"
  commit="$(git -C "$REPO" rev-parse --verify "$oid^{commit}")"
  if git -C "$REPO" merge-base --is-ancestor "$commit" HEAD; then
    tags+=("$tag")
  else
    status=$?
    if [ "$status" -ne 1 ]; then
      echo "error: ancestry check failed for $tag" >&2
      exit "$status"
    fi
  fi
done

total="${#tags[@]}"
if [ "$total" -eq 0 ]; then
  echo "error: no release tags ancestral to HEAD found on origin" >&2
  exit 1
fi

if [ "$total" -le "$COUNT" ]; then
  picked=("${tags[@]}")
elif [ "$COUNT" -eq 1 ]; then
  # One slot means the newest release; there is no span to spread across.
  picked=("${tags[$((total - 1))]}")
else
  # Evenly spaced indices across [0, total-1], endpoints included, so the
  # oldest and newest are always present and the rest are spread between them.
  picked=()
  for slot in $(seq 0 $((COUNT - 1))); do
    # Round to nearest rather than truncate, so the spacing does not bunch
    # toward the oldest end.
    index=$(( (slot * (total - 1) * 2 + (COUNT - 1)) / ((COUNT - 1) * 2) ))
    candidate="${tags[$index]}"
    # Guard against a duplicate if rounding lands twice on the same tag.
    case " ${picked[*]-} " in
      *" $candidate "*) continue ;;
    esac
    picked+=("$candidate")
  done
fi

# Materialize only selected snapshot IDs. Refuse to overwrite divergent
# local tags; a concurrent remote retag cannot change the ancestry we checked.
for tag in "${picked[@]}"; do
  oid="${release_oid[$tag]}"
  if existing="$(git -C "$REPO" rev-parse --verify "refs/tags/$tag" 2>/dev/null)"; then
    if [ "$existing" != "$oid" ]; then
      echo "error: local tag differs from origin snapshot: $tag" >&2
      exit 1
    fi
  else
    git -C "$REPO" update-ref "refs/tags/$tag" "$oid" ''
  fi
done

printf '['
for i in "${!picked[@]}"; do
  [ "$i" -eq 0 ] || printf ','
  printf '"%s"' "${picked[$i]}"
done
printf ']\n'
