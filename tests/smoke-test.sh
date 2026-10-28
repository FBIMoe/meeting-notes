#!/bin/zsh
# smoke-test.sh — run the whole thing end to end in a throwaway home folder, with stand-ins for
# Claude and MacWhisper. Touches nothing of yours: no real notes, no launchd jobs, no Reminders
# (dry-run mode), no notifications. Needs ffmpeg and python3. Takes ~30 seconds.
#
#   tests/smoke-test.sh          → prints PASS/FAIL per step, exits non-zero on any failure
set -u
REPO="${0:A:h:h}"
T=$(mktemp -d /tmp/meeting-notes-test.XXXXXX)
REAL_HOME=$HOME
export HOME="$T/home" MEETING_NOTES_QUIET=1 MEETING_NOTES_DRY_RUN=1
mkdir -p "$HOME" "$T/bin"
fails=0
ok()   { print -r -- "PASS  $*"; }
bad()  { print -r -- "FAIL  $*"; fails=$((fails + 1)); }
check() { local what="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$what"; else bad "$what"; fi; }
age()  { touch -t "$(date -v-5M +%Y%m%d%H%M)" "$@"; }       # look older than the 30-second "still writing" guard
cleanup() { [[ -n "${srv:-}" ]] && kill $srv 2>/dev/null; rm -rf "$T"; }
trap cleanup EXIT

EX="$REPO/examples"
NAME="2026-01-12_Monday team meeting"

# --- stand-ins ------------------------------------------------------------------------------
cat > "$T/bin/claude" <<EOF
#!/bin/zsh
# fake Claude Code: answers by what the prompt asks for
input="\$(cat)"; all="\$* \$input"
if [[ "\$all" == *"TL;DR card"* ]]; then
  print -r -- '{"point":"Weekly team meeting: cycle-count misses, the Dock 4 door, and new stretch wrap.","matters":[{"text":"**Cycle counts** were off on 32 locations","at":"00:22"}],"waiting":[{"who":"Priya Natarajan","what":"List of the 32 locations","due":"Tuesday"}],"todo_at":["00:50"]}'
elif [[ "\$all" == *"Answer the question using ONLY"* ]]; then
  print -r -- "Priya is sending the list of 32 locations by Tuesday."
  print -r -- "— sources: Monday Team Meeting"
else
  cat "$EX/$NAME — OUTPUT.md"
fi
EOF
cat > "$T/bin/mw" <<EOF
#!/bin/zsh
# fake MacWhisper CLI: "transcribes" by copying the example transcript to the -o path
out=""; while (( \$# )); do [[ "\$1" == -o ]] && { out="\$2"; shift; }; shift; done
cp "$EX/$NAME.txt" "\$out"
EOF
chmod +x "$T/bin/"*
export PATH="$T/bin:$PATH"

# --- install ---------------------------------------------------------------------------------
"$REPO/install.sh" --no-jobs --with reminders,app,health </dev/null > "$T/install.out" 2>&1
check "install.sh runs" test -f "$HOME/.meeting-notes/config.sh"
C="$HOME/.meeting-notes/config.sh"
sed -i '' -E "s#^NOTES_DIR=.*#NOTES_DIR=\"$T/notes\"#; s#^EMAIL_DIR=.*#EMAIL_DIR=\"$T/email\"#; s#^APP_PORT=.*#APP_PORT=18787#" "$C"
check "config has the optional parts turned on" grep -q '^REMINDERS=1' "$C"
check "context files copied" test -f "$HOME/.meeting-notes/context/people.md"
source "$C"

# --- transcribe ------------------------------------------------------------------------------
mkdir -p "$INBOX"
ffmpeg -nostdin -v error -f lavfi -i "sine=frequency=440:duration=3" -c:a aac "$INBOX/$NAME.m4a"
age "$INBOX/$NAME.m4a"
"$REPO/pipeline/transcribe.sh" > "$T/transcribe.out" 2>&1
check "transcribe: transcript written" test -s "$TRANSCRIPTS/$NAME.txt"
check "transcribe: audio moved to processed" test -f "$INBOX_DONE/$NAME.m4a"

# --- summarize -------------------------------------------------------------------------------
age "$TRANSCRIPTS/$NAME.txt"
"$REPO/pipeline/summarize.sh" > "$T/summarize.out" 2>&1
note=("$T/notes/Work/"*.md(N))
check "summarize: note filed under Work/" test ${#note} -eq 1
note="${note[1]:-/nonexistent}"
check "summarize: note records its recording" grep -q "^recording: \"$NAME\"" "$note"
check "summarize: email copy written" test -n "$(ls "$T/email" 2>/dev/null)"
check "summarize: transcript moved to processed" test -f "$TRANSCRIPTS_DONE/$NAME.txt"
check "reminders: to-dos pushed (dry run)" grep -q '"done": false' "$STATE/reminders.json"

# --- reminders: note → Reminders ---------------------------------------------------------------
first=$(grep -n -m1 '^- \[ \]' "$note" | cut -d: -f1)
sed -i '' "${first}s/- \[ \]/- [x]/" "$note"
"$PYTHON_BIN" "$REPO/reminders/sync-reminders.py" > "$T/sync.out" 2>&1
check "reminders: ticking a box completes its reminder" grep -q "completed reminder" "$T/sync.out"

# --- app -------------------------------------------------------------------------------------
"$PYTHON_BIN" "$REPO/app/server.py" > "$T/app.out" 2>&1 & srv=$!
for i in {1..30}; do curl -s -o /dev/null http://127.0.0.1:18787/api/data && break; sleep 0.3; done
curl -s -H "Host: 127.0.0.1" http://127.0.0.1:18787/api/data > "$T/data.json"
check "app: /api/data lists the meeting" "$PYTHON_BIN" -c "import json,sys; d=json.load(open('$T/data.json')); assert len(d['meetings'])==1 and d['todos']"
check "app: serves the page" sh -c "curl -s http://127.0.0.1:18787/ | grep -q 'Meeting Notes'"
check "app: rejects a foreign Host header" sh -c "test \$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: evil.example' http://127.0.0.1:18787/api/data) = 403"
check "app: rejects a POST without X-App" sh -c "test \$(curl -s -o /dev/null -w '%{http_code}' -X POST -d '{}' http://127.0.0.1:18787/api/todo) = 403"
check "app: blocks path traversal" sh -c "! curl -s --path-as-is 'http://127.0.0.1:18787/../../../../etc/passwd' | grep -q root:"
for i in {1..40}; do [[ -n $(ls "$STATE/app/tldr" 2>/dev/null) ]] && break; sleep 0.5; done
check "app: TL;DR card built" test -n "$(ls "$STATE/app/tldr" 2>/dev/null)"
tid=$("$PYTHON_BIN" -c "import json; d=json.load(open('$T/data.json')); print([t for t in d['todos'] if not t['done']][0]['id'])")
curl -s -X POST -H 'X-App: 1' -H 'Content-Type: application/json' -d "{\"id\":\"$tid\",\"done\":true}" http://127.0.0.1:18787/api/todo > "$T/todo.json"
check "app: ticking a to-do edits the note" sh -c "test \$(grep -c '^- \[x\]' '$note') -ge 2"
check "app: search finds the meeting" sh -c "curl -s 'http://127.0.0.1:18787/api/search?q=cycle%20count' | grep -q '\"id\"'"
mid=$("$PYTHON_BIN" -c "import json; print(json.load(open('$T/data.json'))['meetings'][0]['id'])")
check "app: audio converts for playback" sh -c "curl -s -o '$T/a.m4a' -w '%{http_code}' http://127.0.0.1:18787/api/audio/$mid.m4a | grep -q 200"
curl -s -X POST -H 'X-App: 1' -d "{\"id\":\"$mid\",\"text\":\"Speaker 3 is Dana Okafor.\"}" http://127.0.0.1:18787/api/fix > "$T/fix.json"
check "app: Fix queues a redo" sh -c "grep -q '\"ok\": true' '$T/fix.json' && test -f '$TRANSCRIPTS/$NAME.txt' && grep -q Okafor '$STATE/meeting-hints/$NAME.txt'"
check "app: redo won't re-push reminders" grep -qxF "$NAME" "$STATE/rerun.list"
kill $srv 2>/dev/null; srv=""

# --- redo lands, then delete ---------------------------------------------------------------------
age "$TRANSCRIPTS/$NAME.txt"
"$REPO/pipeline/summarize.sh" >> "$T/summarize.out" 2>&1
note=("$T/notes/Work/"*.md(N))
check "rerun: new note replaces the old one" test ${#note} -eq 1
check "rerun: rerun.list cleared" sh -c "! grep -qxF '$NAME' '$STATE/rerun.list'"

# --- health check ------------------------------------------------------------------------------
"$REPO/extras/health-check.sh" > "$T/health.out" 2>&1
check "health check runs" grep -q "healthy\|issue" "$T/health.out"

print
if (( fails )); then
  print "$fails check(s) failed. Logs are in $T (kept)."; trap - EXIT; [[ -n "${srv:-}" ]] && kill $srv 2>/dev/null; exit 1
fi
print "All checks passed."
