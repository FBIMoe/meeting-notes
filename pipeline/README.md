# pipeline/: the core

Four background jobs move each recording along, one folder to the next. Every step writes a temp file first and then moves it into place, so no step ever reads a half-written file. A failed step retries 3 times. After that it moves the file to a `*-failed` folder and tells you.

| Script | Runs | Does |
|---|---|---|
| `plaud-pull.sh` | every 15 min | Uses the Plaud CLI to find new recordings from the last `PULL_DAYS` days and downloads the audio into `$INBOX`, named `<date>_<Plaud title>`. It remembers what it has downloaded in `downloaded.txt`. |
| `transcribe.sh` | when `$INBOX` changes, or every 5 min | 1. ffmpeg cleans up the audio (`DENOISE=1`). 2. MacWhisper (`mw`) transcribes with timestamps and speaker labels. 3. pyannote re-splits the speakers (`REDIARIZE=1`, if installed). Optional steps that fail fall back to the previous result. |
| `summarize.sh` | when `$TRANSCRIPTS` changes, or every 5 min | Sends the prompt, your context files, any corrections and the transcript to `claude -p`. Files the note as `NOTES_DIR/<Category>/<date>_<title>.md`. Then: an email copy (never for private notes), and a push to Reminders if that's on. |
| `rerun.sh` | by hand, or from the app's Fix button | Puts a recording back in the queue so its note is rewritten. |
| `rediarize`, `rediarize.py` | called by transcribe.sh | The pyannote step. It runs in its own Python environment, created by `setup-pyannote.sh`. |

## Why pyannote

MacWhisper's built-in speaker split over-counts badly on real meetings. In testing it found 32 to 213 "speakers" in recordings that had 2 to 6 people; a 2-person interview came out as 82. pyannote's `speaker-diarization-community-1` found 2 to 6, matching who was actually there. It takes about 2 minutes for a short meeting and 8 minutes for a 95-minute one on an M-series Mac. It runs offline after the one-time model download.

```zsh
pipeline/setup-pyannote.sh     # needs a free Hugging Face account; the script explains the 3 clicks
```

## Redoing a note

```zsh
pipeline/rerun.sh "<recording name>" "<path to the old note>"           # re-summarize
pipeline/rerun.sh "<recording name>" "<path to the old note>" --audio   # re-transcribe first
```

The old note (and its email copy) move to `~/.meeting-notes/archive/`. A redo never pushes the note's to-dos to Reminders again, because Claude rewords tasks slightly each time and you'd get near-duplicates.

## Folders (all set in config.sh)

`MeetingInbox` → `MeetingInbox-processed` (audio, kept `KEEP_AUDIO_DAYS`) · `MeetingTranscripts` → `MeetingTranscripts-processed` (kept `KEEP_TRANSCRIPT_DAYS`) · `MeetingTranscripts-failed` · `~/.meeting-notes/` (config, prompt, context, corrections, logs)
