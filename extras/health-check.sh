#!/bin/zsh
# health-check.sh — silent-failure insurance. Runs every few hours (launchd) and alerts you ONLY when
# something is wrong: a macOS notification, plus a phone push via ntfy.sh if NTFY_TOPIC is set.
# Prints a one-line status either way (in ~/Library/Logs/meeting-notes/health.log).
#
# Checks: MacWhisper running · background jobs loaded · failed or stuck recordings · NEW error lines
# in the *-errors.log files · Plaud login expired.
set -u
LOG_TAG=health
source "${0:A:h:h}/lib/common.sh"
typeset -a warns

pgrep -x MacWhisper >/dev/null 2>&1 || warns+=("MacWhisper isn't running, so transcription will stall. Open MacWhisper.")

# every job install.sh set up should be loaded
for p in "$HOME/Library/LaunchAgents"/com.meetingnotes.*.plist(N); do
  label="${p:t:r}"
  launchctl list "$label" >/dev/null 2>&1 || warns+=("Background job $label isn't loaded. Re-run ./install.sh.")
done

failed=("$TRANSCRIPTS_FAILED"/*.txt(N))
(( ${#failed} )) && warns+=("${#failed} transcript(s) failed to summarize (in ${TRANSCRIPTS_FAILED:t}). See claude-errors.log, then pipeline/rerun.sh.")

stuck=("$INBOX"/*.(ogg|m4a|mp3|wav)(Nmh+2) "$TRANSCRIPTS"/*.txt(Nmh+2))
(( ${#stuck} )) && warns+=("${#stuck} file(s) waiting for over 2 hours. The pipeline may be stuck.")

# NEW errors only: each log is read from where the last check stopped (byte offsets in
# health-offsets.txt). Otherwise one old error re-alerts every time a good run appends to the log.
# Some tools (mw, ffmpeg, pyannote, ollama) write normal progress to stderr, so for those an
# actual error word is required.
OFFS="$STATE/health-offsets.txt"; typeset -A off; newoffs=()
[[ -f "$OFFS" ]] && while read -r k v; do off[$k]=$v; done < "$OFFS"
for f in "$STATE"/*-errors.log(N); do
  k="${f:t:r}"
  sz=$(stat -f %z "$f" 2>/dev/null || echo 0); from=${off[$k]:-0}; (( sz < from )) && from=0
  newoffs+=("$k $sz")
  (( sz > from )) || continue
  new=$(tail -c +$(( from + 1 )) "$f")
  case "$k" in
    mw-errors|ffmpeg-errors|diarize-errors|llmlocal-errors|pandoc-errors)
      print -r -- "$new" | grep -qiE 'error|fail|exception|traceback' && warns+=("New errors in ${k}.log.") ;;
    *)
      [[ -n "${new//[[:space:]]/}" ]] && warns+=("New errors in ${k}.log.") ;;
  esac
done
print -l -- "${newoffs[@]}" > "$OFFS"

[[ -f "$STATE/plaud-login-expired" ]] && warns+=("Plaud login expired. Run: plaud login")

if (( ${#warns} )); then
  msg="${#warns} issue(s): ${(j: | :)warns}"
  notify "⚠️ $msg"
  [[ -n "$NTFY_TOPIC" ]] && curl -s -m 10 -H "Title: Meeting notes ⚠️" -d "$msg" "https://ntfy.sh/$NTFY_TOPIC" >/dev/null
  log "⚠️ $msg"
else
  log "✅ healthy"
fi
