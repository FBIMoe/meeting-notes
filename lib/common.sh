# common.sh — sourced by every shell script: loads the config and sets up PATH, logging and notifications.
#   source "${0:A:h:h}/lib/common.sh"
CONFIG="${MEETING_NOTES_CONFIG:-$HOME/.meeting-notes/config.sh}"
[[ -r "$CONFIG" ]] || { print -u2 "meeting-notes: no config at $CONFIG — run install.sh first"; exit 1; }
source "$CONFIG"
REPO="${${(%):-%x}:A:h:h}"                     # the repo root (this file lives in <repo>/lib)
export PATH="$NODE_BIN_DIR:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export MEETING_NOTES_CONFIG="$CONFIG"          # so the Python helpers read the same config

log() { print -r -- "$(date '+%F %T') [$LOG_TAG] $*"; }
notify() { [[ -n "${MEETING_NOTES_QUIET:-}" ]] && return; osascript -e "display notification \"${1//\"/\\\"}\" with title \"Meeting notes\"" >/dev/null 2>&1; }

# single-instance lock. Use at the TOP LEVEL of a script (a zsh EXIT trap set inside a function
# fires when the function returns):
#   lock_or_exit pull; trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT
# A lock older than 2 hours is treated as left over from a crash or reboot and cleared.
lock_or_exit() {
  mkdir -p "$STATE"
  LOCKDIR="$STATE/$1.lock"
  mkdir "$LOCKDIR" 2>/dev/null && return
  if [[ -n $(find "$LOCKDIR" -maxdepth 0 -mmin +120 2>/dev/null) ]]; then
    rmdir "$LOCKDIR" 2>/dev/null; mkdir "$LOCKDIR" 2>/dev/null && return
  fi
  exit 0                                        # another run is active
}

# true if the file was modified in the last 30s (still being written)
too_fresh() { (( $(date +%s) - $(stat -f %m "$1") < 30 )); }
