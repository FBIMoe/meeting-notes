#!/bin/zsh
# plaud-pull.sh — download new Plaud recordings into $INBOX.
# Uses the Plaud CLI (`plaud login` once). Remembers what it already downloaded in $STATE/downloaded.txt.
set -u
LOG_TAG=pull
source "${0:A:h:h}/lib/common.sh"
SEEN="$STATE/downloaded.txt"

mkdir -p "$INBOX" "$STATE"; touch "$SEEN"
lock_or_exit pull; trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT
cd "$STATE"

# Filename = <recording date>_<recording title>, made filesystem-safe; falls back to the id.
name_for() {
  local id="$1" details rname rdate
  details=$(plaud file "$id" 2>/dev/null) || { print -r -- "$(date +%F)_$id"; return; }
  rname=$(print -r -- "$details" | sed -n 's/^[[:space:]]*name:[[:space:]]*//p' | head -1)
  rdate=$(print -r -- "$details" | sed -nE 's/^[[:space:]]*(start_at|created_at):[[:space:]]*([0-9]{4}-[0-9]{2}-[0-9]{2}).*/\2/p' | head -1)
  [[ -z "$rdate" ]] && rdate=$(date +%F)
  rname=$(print -r -- "$rname" | sed -E 's#[/:\\<>|?*"]+# #g; s/[[:space:]]+/ /g; s/^ +//; s/ +$//')
  if (( ${#rname} > 60 )); then rname=${rname[1,60]}; rname=${rname% *}; fi
  print -r -- "${rdate}_${rname:-$id}"
}

list=$(plaud recent --days "$PULL_DAYS" 2>&1); rc=$?
if (( rc != 0 )); then
  if (( rc == 2 )) || print -r -- "$list" | grep -qiE 'auth|login|token'; then
    touch "$STATE/plaud-login-expired"           # health-check.sh reports it until a pull works again
    notify "Plaud login expired. Run: plaud login"; log "auth failed (rc=$rc)"; exit 1
  fi
  log "plaud recent failed (rc=$rc): $list"; exit 1
fi
rm -f "$STATE/plaud-login-expired"

for id in ${(f)"$(print -r -- "$list" | grep -oE 'of_[0-9a-f]{32}' | sort -u)"}; do
  [[ -z "$id" ]] && continue
  grep -qxF "$id" "$SEEN" && continue
  url=$(plaud audio "$id" 2>/dev/null | grep -oE 'https://[^[:space:]"]+' | head -1)
  if [[ -z "$url" ]]; then log "audio not ready: $id"; continue; fi

  base=$(name_for "$id")
  dest="$INBOX/$base.ogg"
  [[ -e "$dest" ]] && dest="$INBOX/${base}_${id[4,11]}.ogg"
  tmp="$STATE/$id.ogg.part"
  if curl -sfL --retry 3 "$url" -o "$tmp" && [[ -s "$tmp" ]]; then
    mv "$tmp" "$dest"                          # atomic: the transcriber never sees a partial file
    print -r -- "$id" >> "$SEEN"
    log "downloaded $id -> ${dest:t}"
  else
    rm -f "$tmp"; log "download failed: $id"
  fi
done
