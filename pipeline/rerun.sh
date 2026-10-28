#!/bin/zsh
# rerun.sh — regenerate a note after you change the prompt, your context files, or a correction.
#
#   rerun.sh "<recording name>" ["<path to the old note>"] [--audio]
#
#   <recording name>  the transcript/audio name without extension, e.g. "2026-01-15_Team sync"
#                     (it's also in each note's frontmatter as `recording:`)
#   old note          optional; moved to $STATE/archive/ so you don't end up with two versions
#   --audio           re-TRANSCRIBE from the original audio (use after changing transcription or
#                     speaker settings) instead of re-summarizing the existing transcript
#
# Works for transcripts that failed too (it looks in $TRANSCRIPTS_FAILED). A re-run never pushes the
# note's to-dos to Reminders a second time.
set -u
LOG_TAG=rerun
source "${0:A:h:h}/lib/common.sh"

name="${1:-}"; old="${2:-}"; mode="${3:-}"
[[ -n "$name" ]] || { print -u2 "usage: rerun.sh \"<recording name>\" [\"<old note>\"] [--audio]"; exit 2; }
[[ "$old" == "--audio" ]] && { mode="--audio"; old=""; }
A="$STATE/archive"; mkdir -p "$A"

# check the source exists BEFORE archiving anything
if [[ "$mode" == "--audio" ]]; then
  audio=( "$INBOX_DONE/$name".(ogg|m4a|mp3|wav)(N) )
  (( ${#audio} )) || { echo "no audio for: $name"; exit 1; }
else
  src=( "$TRANSCRIPTS_DONE/$name.txt"(N) "$TRANSCRIPTS_FAILED/$name.txt"(N) )
  (( ${#src} )) || { echo "no transcript for: $name"; exit 1; }
fi

if [[ -n "$old" ]]; then
  [[ -f "$old" ]] && mv "$old" "$A/" && echo "archived ${old:t}"
  [[ -n "$EMAIL_DIR" && -f "$EMAIL_DIR/${old:t:r}.txt" ]] && mv "$EMAIL_DIR/${old:t:r}.txt" "$A/" && echo "archived email copy"
fi
grep -qxF "$name" "$STATE/rerun.list" 2>/dev/null || print -r -- "$name" >> "$STATE/rerun.list"

if [[ "$mode" == "--audio" ]]; then
  [[ -f "$TRANSCRIPTS_DONE/$name.txt" ]] && mv "$TRANSCRIPTS_DONE/$name.txt" "$A/"
  mv "$audio[1]" "$INBOX/" && touch -t "$(date -v-1M +%Y%m%d%H%M)" "$INBOX/${audio[1]:t}" && echo "queued $name for re-transcription"
else
  mv "$src[1]" "$TRANSCRIPTS/" && touch -t "$(date -v-1M +%Y%m%d%H%M)" "$TRANSCRIPTS/$name.txt" && echo "queued $name for re-summary"
fi
