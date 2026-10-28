#!/bin/zsh
# summarize.sh — transcript in $TRANSCRIPTS → Markdown meeting note in $NOTES_DIR/<Category>/ via Claude Code.
# Claude gets: the meeting prompt + your context files (about-me, people, vocabulary) + any per-recording
# corrections. Then, optionally: a plain-text copy to $EMAIL_DIR (never for private notes) and your
# to-dos pushed to Apple Reminders. If Claude fails 3 times and LOCAL_MODEL is set, a clearly-flagged
# local draft is written instead so the meeting is never lost.
set -u
LOG_TAG=sum
source "${0:A:h:h}/lib/common.sh"
unset ANTHROPIC_API_KEY        # bill your Claude subscription, never the pay-per-token API

PROMPT_FILE="$STATE/meeting-prompt.md"
CTX="$STATE/context"
mkdir -p "$TRANSCRIPTS" "$TRANSCRIPTS_DONE" "$TRANSCRIPTS_FAILED" "$NOTES_DIR" "$STATE"
lock_or_exit summarize; trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT
cd "$STATE"                    # so claude never picks up a stray CLAUDE.md from elsewhere

# section <file> <heading> — prints the file under a heading, or nothing if it's missing/empty
section() { [[ -s "$1" ]] && print -r -- "

$2
$(cat "$1")"; }

for f in "$TRANSCRIPTS"/*.txt(N); do
  too_fresh "$f" && continue
  name="${f:t:r}"
  tmp="$STATE/$name.md.tmp"

  prompt="$(cat "$PROMPT_FILE")$(section "$CTX/about-me.md" "ABOUT THE USER (the person who made the recording):")$(
    section "$CTX/people.md" "KNOWN PEOPLE (use for correct spelling, and to attribute a Speaker to a real person when the transcript gives a hint; never invent or force a match):")$(
    section "$CTX/vocabulary.md" "VOCABULARY (spell these correctly; fix obvious mis-transcriptions to the listed form):")$(
    section "$STATE/meeting-hints/$name.txt" "CORRECTIONS FROM THE USER FOR THIS RECORDING (authoritative — override anything you would infer; use for attendees, speaker attribution and spelling):")

Recording filename: $name"

  if "$CLAUDE_BIN" -p "$prompt" < "$f" > "$tmp" 2>>"$STATE/claude-errors.log" && [[ -s "$tmp" ]]; then
    # Record which recording produced this note (the app uses it for audio, fixes and photos).
    if [[ "$(head -1 "$tmp")" == "---" ]]; then
      awk -v r="${name//\"/}" 'NR==1 {print; print "recording: \"" r "\""; next} {print}' "$tmp" > "$tmp.r" && mv "$tmp.r" "$tmp"
    fi
    fm() { sed -n "s/^$1:[[:space:]]*//p" "$tmp" | head -1; }
    category=$(fm category | tr -d '[:space:]')
    case "$category" in Work|Personal|Learning|Training|Ideas|Inbox) ;; *) category="Inbox" ;; esac
    private=$(fm private | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
    title=$(fm title)
    [[ -z "$title" ]] && title=$(grep -m1 '^#[[:space:]]' "$tmp" | sed -E 's/^#[[:space:]]+//')
    title=$(print -r -- "$title" | sed -E 's#[/:\\<>|?*"]+# #g; s/[[:space:]]+/ /g; s/^ +//; s/ +$//')
    if (( ${#title} > 60 )); then title=${title[1,60]}; title=${title% *}; fi
    title=$(print -r -- "$title" | sed -E 's/[[:space:]]*[([{][^])}]*$//; s/[[:space:],;:.]+$//')

    datepref="${name%%_*}"
    [[ "$datepref" =~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' ]] || datepref="$(date +%F)"
    base="${datepref}_${title:-$name}"
    dir="$NOTES_DIR/$category"; mkdir -p "$dir"
    dest="$dir/$base.md"
    [[ -e "$dest" ]] && dest="$dir/${base}_$(date +%H%M%S).md"
    mv "$tmp" "$dest"                            # atomic: your notes app never syncs a partial note
    log "filed under $category/"

    # Plain-text copy for email — never for private notes. The frontmatter is stripped first: the
    # plain copy doesn't show it, and a ":" in a title makes it invalid YAML for pandoc.
    if [[ -n "$EMAIL_DIR" && "$private" != "true" ]]; then
      mkdir -p "$EMAIL_DIR"
      if awk 'NR==1 && /^---$/ {fm=1; next} fm && /^---$/ {fm=0; next} !fm' "$dest" \
           | "$PANDOC_BIN" -f markdown -t plain --wrap=none -o "$EMAIL_DIR/${dest:t:r}.txt" 2>>"$STATE/pandoc-errors.log"; then
        log "email copy -> ${dest:t:r}.txt"
      else
        log "email copy failed for $name"
      fi
    fi

    # To-dos → Apple Reminders. A re-run (rerun.sh adds the name to rerun.list) does NOT push again:
    # Claude rewords tasks a little each time, so a second push would make near-duplicates.
    if grep -qxF "$name" "$STATE/rerun.list" 2>/dev/null; then
      grep -vxF "$name" "$STATE/rerun.list" > "$STATE/rerun.list.tmp"; mv "$STATE/rerun.list.tmp" "$STATE/rerun.list"
      (( REMINDERS )) && log "re-run — reminders not pushed again"
    elif (( REMINDERS )); then
      "$PYTHON_BIN" "$REPO/reminders/push-reminders.py" "$dest" >>"$STATE/reminders.log" 2>>"$STATE/reminders-errors.log" \
        || log "reminders push failed (continuing) — see reminders-errors.log"
    fi

    mv "$f" "$TRANSCRIPTS_DONE/"
    rm -f "$STATE/fail_$name"
    log "summarized $name"
    notify "New meeting note: ${title:-$name}"
  else
    rm -f "$tmp"
    cnt="$STATE/fail_$name"
    n=$(( $(cat "$cnt" 2>/dev/null || echo 0) + 1 )); echo $n > "$cnt"
    log "claude failed for $name (attempt $n)"
    if (( n >= 3 )); then
      # Keep the transcript in $TRANSCRIPTS_FAILED so it can go through Claude later (rerun.sh).
      if [[ -n "$LOCAL_MODEL" ]] && "$REPO/extras/local-draft.sh" "$f" >>"$STATE/local-draft.log" 2>>"$STATE/llmlocal-errors.log"; then
        log "claude unavailable — wrote a local draft for $name"
        notify "Claude was down — saved a local draft: $name"
      else
        notify "Summary failed 3x: $name"
      fi
      mv "$f" "$TRANSCRIPTS_FAILED/"; rm -f "$cnt"
    fi
  fi
done

find "$TRANSCRIPTS_DONE" -type f -mtime +"$KEEP_TRANSCRIPT_DAYS" -delete 2>/dev/null
