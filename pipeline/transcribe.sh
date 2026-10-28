#!/bin/zsh
# transcribe.sh — audio in $INBOX → speaker-labeled, timestamped transcript in $TRANSCRIPTS.
#   1. (optional) ffmpeg denoise/normalize
#   2. MacWhisper CLI (`mw`) transcribes with its own speaker labels
#   3. (optional) pyannote re-splits the speakers (much better at "who spoke when")
# Any optional step that fails falls back to the previous result — it can only help, never block.
set -u
LOG_TAG=txt
source "${0:A:h:h}/lib/common.sh"

mkdir -p "$INBOX" "$INBOX_DONE" "$TRANSCRIPTS" "$TRANSCRIPTS_FAILED" "$STATE"
lock_or_exit transcribe; trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT
cd "$STATE"

for f in "$INBOX"/*.(ogg|m4a|mp3|wav)(N); do
  too_fresh "$f" && continue
  name="${f:t:r}"
  tmp="$STATE/$name.txt"
  rm -f "$tmp"

  src="$f"
  if (( DENOISE )); then
    clean="$STATE/$name.clean.wav"
    if "$FFMPEG_BIN" -nostdin -y -i "$f" -af "highpass=f=90,afftdn=nf=-20,loudnorm=I=-16:TP=-1.5:LRA=11" \
         -ar 16000 -ac 1 "$clean" >>"$STATE/ffmpeg-errors.log" 2>&1 && [[ -s "$clean" ]]; then
      src="$clean"
    else
      rm -f "$clean"; log "denoise failed for $name — using original audio"
    fi
  fi

  if "$MW_BIN" transcribe "$src" --format txt --style segments --speakers --speaker-names --timestamps \
       --overwrite -o "$tmp" 2>>"$STATE/mw-errors.log" && [[ -s "$tmp" ]]; then
    if (( REDIARIZE )) && [[ -x "${PYANNOTE_VENV:-$STATE/pyannote-venv}/bin/python" ]]; then
      if "$REPO/pipeline/rediarize" --transcript "$tmp" --audio "$src" --out "$tmp.rd" 2>>"$STATE/diarize-errors.log" \
           && [[ -s "$tmp.rd" ]]; then
        mv "$tmp.rd" "$tmp"; log "re-diarized $name"
      else
        rm -f "$tmp.rd"
      fi
    fi
    mv "$tmp" "$TRANSCRIPTS/$name.txt"           # atomic: the summarizer never sees a partial file
    mv "$f" "$INBOX_DONE/"
    rm -f "$STATE/txfail_$name"
    log "transcribed $name"
  else
    rm -f "$tmp"
    cnt="$STATE/txfail_$name"
    n=$(( $(cat "$cnt" 2>/dev/null || echo 0) + 1 )); echo $n > "$cnt"
    log "mw failed for $name (attempt $n)"
    if (( n >= 3 )); then
      mv "$f" "$TRANSCRIPTS_FAILED/"; rm -f "$cnt"
      notify "Transcription failed 3x: $name"
    fi
  fi
  rm -f "$STATE/$name.clean.wav"
done

find "$INBOX_DONE" -type f -mtime +"$KEEP_AUDIO_DAYS" -delete 2>/dev/null
