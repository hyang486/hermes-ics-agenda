#!/usr/bin/env bash
# Fresh-install verification for the ics-agenda Hermes skill tap.
#
# Usage:
#   OWNER_REPO=<owner>/<repo> scripts/fresh_install_test.sh            # auto: docker > local hermes > print
#   OWNER_REPO=<owner>/<repo> MODE=docker scripts/fresh_install_test.sh
#   OWNER_REPO=<owner>/<repo> MODE=local  scripts/fresh_install_test.sh
#   OWNER_REPO=<owner>/<repo> MODE=print  scripts/fresh_install_test.sh  # only print the commands
#
# The script:
#   1. creates a throwaway HERMES_HOME under /tmp (never touches ~/.hermes)
#   2. runs the official image nousresearch/hermes-agent:v0.22.7 if docker exists,
#      else a local `hermes` on PATH, else just prints the commands
#   3. runs `hermes skills tap add OWNER/REPO` and `hermes skills install OWNER/REPO/ics-agenda`,
#      then runs the installed script on its bundled synthetic sample calendar
#   4. writes the transcript to transcripts/fresh_install_<timestamp>.log
#
# The repo must already be public on GitHub (installs from a direct SKILL.md URL are
# not used). GITHUB_TOKEN is passed through only if it is set (it helps with rate limits).
set -euo pipefail

OWNER_REPO="${OWNER_REPO:-${1:-}}"
if [[ -z "$OWNER_REPO" || "$OWNER_REPO" != */* ]]; then
  echo "error: set OWNER_REPO=<owner>/<repo> (or pass it as the first argument)" >&2
  exit 2
fi
IMAGE="${HERMES_IMAGE:-nousresearch/hermes-agent:v0.22.7}"
MODE="${MODE:-auto}"
NOW_PIN="2026-11-16T08:00"   # pins 'now' so the sample output is reproducible

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$REPO_ROOT/transcripts"
LOG="$REPO_ROOT/transcripts/fresh_install_${TS}.log"
HH="$(mktemp -d /tmp/hermes-fresh-XXXXXX)"
chmod 700 "$HH"

if [[ "$MODE" == auto ]]; then
  if command -v docker >/dev/null 2>&1; then MODE=docker
  elif command -v hermes >/dev/null 2>&1; then MODE=local
  else MODE=print; fi
fi

# --- how to invoke hermes / a shell inside the chosen environment -------------------
CONTAINER_HOME=/hermes-home
docker_base=(docker run --rm -i -e HERMES_HOME="$CONTAINER_HOME" -v "$HH:$CONTAINER_HOME")
[[ -n "${GITHUB_TOKEN:-}" ]] && docker_base+=(-e GITHUB_TOKEN)

hermes_cmd() {   # hermes_cmd <args...>
  case "$MODE" in
    docker) "${docker_base[@]}" --entrypoint hermes "$IMAGE" "$@" ;;
    local)  HERMES_HOME="$HH" hermes "$@" ;;
  esac
}
shell_cmd() {    # shell_cmd '<bash snippet>'  (HERMES_HOME is set inside)
  case "$MODE" in
    docker) "${docker_base[@]}" --entrypoint bash "$IMAGE" -lc "$1" ;;
    local)  HERMES_HOME="$HH" bash -c "$1" ;;
  esac
}
step() { printf '\n$ %s\n' "$*"; }

# Locate the installed skill dir (layout may include a category folder).
FIND_SKILL='d=$(find "$HERMES_HOME/skills" -type f -path "*ics-agenda/scripts/ics_agenda.py" 2>/dev/null | head -1); d=${d%/scripts/ics_agenda.py}; [ -n "$d" ] || { echo "ics-agenda not found under $HERMES_HOME/skills" >&2; exit 1; }'
RUN_SKILL="$FIND_SKILL"'
echo "installed skill dir: ${d#$HERMES_HOME/}"
echo "--- SKILL.md frontmatter ---"; sed -n "1,/^---$/{p}" "$d/SKILL.md" | sed -n "1,15p"
for args in "agenda --days 3" "conflicts --days 7" "free --date 2026-11-16 --min 45" "next" "agenda --days 2 --details"; do
  echo; echo "\$ python3 \${HERMES_SKILL_DIR}/scripts/ics_agenda.py $args --source \${HERMES_SKILL_DIR}/assets/sample.ics --now '"$NOW_PIN"'"
  python3 "$d/scripts/ics_agenda.py" $args --source "$d/assets/sample.ics" --now '"$NOW_PIN"'
done'

if [[ "$MODE" == print ]]; then
  cat <<EOF | tee "$LOG"
# Neither docker nor hermes was found. Run these on a machine with one of them:
export HERMES_HOME=\$(mktemp -d /tmp/hermes-fresh-XXXXXX)
# docker:  alias hermes='docker run --rm -i -e HERMES_HOME=/hermes-home -v \$HERMES_HOME:/hermes-home --entrypoint hermes $IMAGE'
hermes --version
hermes skills tap add $OWNER_REPO
hermes skills tap list
hermes skills install $OWNER_REPO/ics-agenda
hermes skills list
python3 \$HERMES_HOME/skills/**/ics-agenda/scripts/ics_agenda.py agenda --days 3 \\
  --source \$HERMES_HOME/skills/**/ics-agenda/assets/sample.ics --now $NOW_PIN
EOF
  exit 3
fi

set +e
{
  set -e
  echo "# ics-agenda fresh-install transcript"
  echo "# date (UTC): $TS   mode: $MODE   image: $([[ $MODE == docker ]] && echo "$IMAGE" || echo n/a)"
  echo "# tap: $OWNER_REPO   commit under test: ${COMMIT:-<set COMMIT=... to record>}"
  echo "# HERMES_HOME: fresh temp dir (empty before this run)"
  [[ "$MODE" == docker ]] && { step docker pull "$IMAGE"; docker pull "$IMAGE" 2>&1 | tail -2; }
  step ls -A '$HERMES_HOME'; ls -A "$HH"; echo "(empty)"
  step hermes --version;                                  hermes_cmd --version
  step hermes skills tap add "$OWNER_REPO";               hermes_cmd skills tap add "$OWNER_REPO"
  step hermes skills tap list;                            hermes_cmd skills tap list
  # New taps are 'community' trust: the install runs a security scan and may ask for
  # confirmation, so a 'y' is piped in. (UNVERIFIED: whether v0.22.7 prompts here.)
  step hermes skills install "$OWNER_REPO/ics-agenda";    printf 'y\n' | hermes_cmd skills install "$OWNER_REPO/ics-agenda"
  step hermes skills list;                                hermes_cmd skills list | grep -iE 'ics-agenda|name' || true
  step "# run the installed skill on its bundled synthetic sample"
  shell_cmd "$RUN_SKILL"
  echo; echo "# result: OK"
} 2>&1 | tee "$LOG"
rc=${PIPESTATUS[0]}
set -e
echo "transcript: $LOG"
echo "throwaway HERMES_HOME left at $HH (rm -rf it when done)"
exit "$rc"
