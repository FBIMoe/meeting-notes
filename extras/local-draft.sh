#!/bin/zsh
# local-draft.sh <transcript.txt> — write a clearly-flagged draft note with a LOCAL Ollama model.
#
# summarize.sh calls this when Claude has failed 3 times and LOCAL_MODEL is set, so a meeting is never
# lost when Claude is down. Free, offline, private — but a small model is noticeably worse at the hard
# parts (who said what, who owns which task), so the draft says so and keeps no checkboxes.
# The transcript is kept in $TRANSCRIPTS_FAILED; `pipeline/rerun.sh "<name>" "<draft note>"` replaces
# the draft with a real note once Claude is back.
set -u
LOG_TAG=local
source "${0:A:h:h}/lib/common.sh"

f="${1:?usage: local-draft.sh <transcript.txt>}"
name="${f:t:r}"
[[ -n "$LOCAL_MODEL" ]] || { print -u2 "local-draft: LOCAL_MODEL is not set in config.sh"; exit 2; }
[[ -x "$OLLAMA_BIN" ]] || { print -u2 "local-draft: ollama not found at $OLLAMA_BIN (brew install ollama)"; exit 3; }

# Ollama isn't always running as a service; start it if needed.
if ! curl -s --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  "$OLLAMA_BIN" serve >/dev/null 2>&1 &
  for i in {1..20}; do
    curl -s --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
    sleep 0.5
  done
fi

instructions="Summarize this meeting transcript. Write plain Markdown with only these sections, and only if relevant:
## Summary (2-4 sentences)
## Key Points (bullets)
## Possible Action Items (plain bullets with who said they'd do it, no checkboxes)
Use only what is in the transcript. Do not invent names, numbers or decisions. No preamble, no YAML frontmatter."

draft="$STATE/$name.local.md"
print -r -- "$instructions

TRANSCRIPT:
$(cat "$f")" | "$OLLAMA_BIN" run "$LOCAL_MODEL" > "$draft" || { rm -f "$draft"; exit 1; }
[[ -s "$draft" ]] || { rm -f "$draft"; exit 1; }

title=$(print -r -- "${name#*_}" | sed -E 's/[_-]+/ /g; s/^ +//; s/ +$//'); [[ -z "$title" ]] && title="$name"
day="${name%%_*}"; [[ "$day" =~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' ]] || day="$(date +%F)"
dir="$NOTES_DIR/Inbox"; mkdir -p "$dir"
dest="$dir/${day}_${title} (local draft).md"
[[ -e "$dest" ]] && dest="$dir/${day}_${title} (local draft)_$(date +%H%M%S).md"
{
  print -r -- "---"
  print -r -- "title: \"${title//\"/} (local draft)\""
  print -r -- "date: $day"
  print -r -- "category: Inbox"
  print -r -- "type: note"
  print -r -- "tags: [local-draft]"
  print -r -- "recording: \"${name//\"/}\""
  print -r -- "---"
  print -r --
  print -r -- "> **Local draft ($LOCAL_MODEL).** Claude was unavailable, so this is a rougher offline summary."
  print -r -- "> Replace it once Claude is back: \`pipeline/rerun.sh \"$name\" \"<this note>\"\`"
  print -r --
  cat "$draft"
} > "$STATE/$name.draft.tmp" && mv "$STATE/$name.draft.tmp" "$dest"
rm -f "$draft"
log "local draft -> ${dest:t}"
