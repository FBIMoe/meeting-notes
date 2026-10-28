#!/bin/zsh
# install.sh — set up meeting-notes on this Mac.
#
#   ./install.sh                      the core pipeline, then asks about each optional part
#   ./install.sh --with app,reminders turn on optional parts without asking
#                                     (parts: reminders, app, health, local; or "all")
#   ./install.sh --no-jobs            config + context files only (run the scripts by hand)
#   ./install.sh --uninstall          remove the background jobs (your notes and config are left alone)
#
# Safe to re-run: it never overwrites your config, prompt or context files. Re-run it to add a part
# later, or after moving this folder (the background jobs point at wherever the repo is).
set -eu
REPO="${0:A:h}"
DEST="${MEETING_NOTES_HOME:-$HOME/.meeting-notes}"
CONFIG="$DEST/config.sh"
AGENTS="$HOME/Library/LaunchAgents"
LOGDIR="$HOME/Library/Logs/meeting-notes"
ALL_JOBS=(pull transcribe summarize reminders health app)

say() { print -r -- "• $*"; }
ask() {                                     # ask "question" → 0 for yes. Non-interactive = no.
  [[ -t 0 ]] || return 1
  local a; read -r "a?  $1 [y/N] "; [[ "$a" == [yY]* ]]
}
setcfg() {                                  # setcfg KEY VALUE — change one line in config.sh
  sed -i '' -E "s#^$1=[^ ]*#$1=$2#" "$CONFIG"
}

if [[ "${1:-}" == "--uninstall" ]]; then
  for j in $ALL_JOBS; do
    launchctl bootout "gui/$(id -u)/com.meetingnotes.$j" 2>/dev/null || true
    rm -f "$AGENTS/com.meetingnotes.$j.plist"
  done
  say "Background jobs removed. Your notes and $DEST were not touched."
  exit 0
fi
want=""; nojobs=""
while (( $# )); do
  case "$1" in
    --with) want="${2:-}"; shift ;;
    --with=*) want="${1#--with=}" ;;
    --no-jobs) nojobs=1 ;;
    *) print -u2 "unknown option: $1"; exit 2 ;;
  esac
  shift
done
[[ "$want" == all ]] && want="reminders,app,health,local"

# --- check tools ---------------------------------------------------------------------------
missing=()
claude_bin=$(command -v claude || true)
python_bin=$(command -v python3 || true)
mw_bin=$(command -v mw || { [[ -x /usr/local/bin/mw ]] && echo /usr/local/bin/mw; } || true)
[[ -n "$claude_bin" ]] || missing+=("Claude Code CLI (npm install -g @anthropic-ai/claude-code, then run 'claude' once to log in)")
[[ -n "$mw_bin" ]] || missing+=("MacWhisper CLI 'mw' (MacWhisper Pro → Settings → install the command line tool)")
command -v ffmpeg >/dev/null || missing+=("ffmpeg (brew install ffmpeg)")
[[ -n "$python_bin" ]] || missing+=("python3 (xcode-select --install, or brew install python)")
command -v pandoc >/dev/null || say "pandoc not found — fine unless you want email copies (brew install pandoc)"
command -v plaud  >/dev/null || say "Plaud CLI not found — fine if you drop audio files into the inbox yourself"
if (( ${#missing} )); then
  print -r -- "Missing:"; for m in $missing; do print -r -- "  - $m"; done; exit 1
fi

# --- config, prompt, context ---------------------------------------------------------------
mkdir -p "$DEST/context" "$DEST/meeting-hints"; chmod 700 "$DEST" "$DEST/meeting-hints"
if [[ ! -f "$CONFIG" ]]; then
  sed -e "s#__CLAUDE_BIN__#$claude_bin#" -e "s#__NODE_BIN_DIR__#${claude_bin:h}#" -e "s#__PYTHON_BIN__#$python_bin#" -e "s#__MW_BIN__#$mw_bin#" \
      -e "s#__FFMPEG_BIN__#$(command -v ffmpeg)#" -e "s#__PANDOC_BIN__#$(command -v pandoc || echo /opt/homebrew/bin/pandoc)#" \
      -e "s#^STATE=.*#STATE=\"$DEST\"#" \
      "$REPO/config.example.sh" > "$CONFIG"
  say "Wrote $CONFIG — open it and set NOTES_DIR (and EMAIL_DIR if you want email copies)."
else
  say "Kept your existing $CONFIG"
fi
[[ -f "$DEST/meeting-prompt.md" ]] || { cp "$REPO/prompts/meeting-prompt.md" "$DEST/"; say "Copied the meeting prompt to $DEST/meeting-prompt.md"; }
for f in "$REPO/examples/context/"*.md; do
  [[ -f "$DEST/context/${f:t}" ]] || { cp "$f" "$DEST/context/"; say "Copied example ${f:t} — replace it with your own"; }
done
chmod +x "$REPO"/pipeline/*.sh "$REPO/pipeline/rediarize" "$REPO"/extras/*.sh "$REPO/reminders/push-reminders.py" "$REPO/reminders/sync-reminders.py" "$REPO/app/server.py"

# --- optional parts --------------------------------------------------------------------------
source "$CONFIG"
part() {                                    # part <name> <question> — on if --with names it, or the user says yes
  [[ ",$want," == *",$1,"* ]] && return 0
  [[ -z "$want" ]] && ask "$2"
}
on=()
if (( REMINDERS )) || part reminders "Send your to-dos to Apple Reminders (and keep ticks in sync both ways)?"; then
  setcfg REMINDERS 1; on+=(reminders)
fi
if [[ -f "$AGENTS/com.meetingnotes.app.plist" ]] || part app "Run the Meeting Notes app (read and act on notes from your phone)?"; then
  on+=(app)
  if [[ ! -x "$REPO/extras/ocr-image" ]] && command -v swiftc >/dev/null; then
    swiftc -O "$REPO/extras/ocr-image.swift" -o "$REPO/extras/ocr-image" 2>/dev/null \
      && say "Built extras/ocr-image (reads text in photos you add in the app, on-device)" \
      || say "Couldn't build extras/ocr-image — photos will still save, their text just won't be read"
  fi
fi
if [[ -f "$AGENTS/com.meetingnotes.health.plist" ]] || part health "Run a health check every 6 hours that alerts you only when something breaks?"; then
  on+=(health)
fi
if [[ -n "$LOCAL_MODEL" ]] || part local "Use a local Ollama model as a backup when Claude is unavailable?"; then
  if [[ -z "$LOCAL_MODEL" ]]; then
    setcfg LOCAL_MODEL '"qwen2.5:3b"'
    say "Set LOCAL_MODEL=qwen2.5:3b — run: brew install ollama && ollama pull qwen2.5:3b (or pick another model in config.sh)"
  fi
  on+=(local)
fi
source "$CONFIG"

[[ -n "$nojobs" ]] && { say "Skipped background jobs (--no-jobs)."; exit 0; }

# --- background jobs (launchd) -------------------------------------------------------------
mkdir -p "$AGENTS" "$LOGDIR" "$INBOX" "$TRANSCRIPTS"
s() { print -r -- "<string>$1</string>"; }
jobs=(transcribe summarize)
command -v plaud >/dev/null && jobs=(pull $jobs) || say "Skipping the Plaud pull job (no Plaud CLI)."
(( ${on[(Ie)reminders]} )) && jobs+=(reminders)
(( ${on[(Ie)health]} )) && jobs+=(health)
(( ${on[(Ie)app]} )) && jobs+=(app)
for j in $jobs; do
  case $j in
    pull)       args="$(s /bin/zsh)$(s $REPO/pipeline/plaud-pull.sh)"; sched="<key>StartInterval</key><integer>900</integer>" ;;
    transcribe) args="$(s /bin/zsh)$(s $REPO/pipeline/transcribe.sh)"
                sched="<key>StartInterval</key><integer>300</integer><key>WatchPaths</key><array>$(s $INBOX)</array>" ;;
    summarize)  args="$(s /bin/zsh)$(s $REPO/pipeline/summarize.sh)"
                sched="<key>StartInterval</key><integer>300</integer><key>WatchPaths</key><array>$(s $TRANSCRIPTS)</array>" ;;
    reminders)  args="$(s $PYTHON_BIN)$(s $REPO/reminders/sync-reminders.py)"; sched="<key>StartInterval</key><integer>900</integer>" ;;
    health)     args="$(s /bin/zsh)$(s $REPO/extras/health-check.sh)"; sched="<key>StartInterval</key><integer>21600</integer>" ;;
    app)        args="$(s $PYTHON_BIN)$(s $REPO/app/server.py)"; sched="<key>KeepAlive</key><true/>" ;;
  esac
  plist="$AGENTS/com.meetingnotes.$j.plist"
  sed -e "s#__LABEL__#com.meetingnotes.$j#" -e "s#__ARGS__#$args#" -e "s#__SCHEDULE__#$sched#" \
      -e "s#__CONFIG__#$CONFIG#" -e "s#__LOGDIR__#$LOGDIR#" -e "s#__NAME__#$j#" "$REPO/launchd/job.plist.template" > "$plist"
  plutil -lint -s "$plist" || { print -u2 "bad plist: $plist"; exit 1; }
  launchctl bootout "gui/$(id -u)/com.meetingnotes.$j" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$plist"
  say "Started background job: $j"
done

say "Done. Logs: $LOGDIR"
print
print "Next:"
print "  1. Edit $CONFIG — at least NOTES_DIR."
print "  2. Replace the example files in $DEST/context/ with your own (see README)."
print "  3. Optional, recommended: $REPO/pipeline/setup-pyannote.sh for much better speaker separation."
(( ${on[(Ie)reminders]} )) && print "  • Reminders: macOS will ask to let python3 control Reminders the first time — click OK."
(( ${on[(Ie)app]} )) && print "  • App: open http://127.0.0.1:$APP_PORT on this Mac. For your phone, see app/README.md (Tailscale)."
true
