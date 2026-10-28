# meeting-notes config — install.sh copies this to ~/.meeting-notes/config.sh. Edit that copy, not this one.
# Every script (shell and Python) reads it, so this is the ONLY place your paths and settings live.

# --- Where things go -------------------------------------------------------------------------
# Folder for your meeting notes. Any folder of Markdown works: an Obsidian vault folder, iCloud Drive,
# or just ~/Documents. Notes are filed into subfolders by category (Work, Personal, Training, ...).
NOTES_DIR="$HOME/Documents/Meeting Notes"
# Optional: a folder for plain-text, email-ready copies of each note (e.g. an iCloud Drive folder you
# can open on your phone). Private notes never get one. Leave empty to turn this off.
EMAIL_DIR=""

# Working folders (fine to leave as-is).
INBOX="$HOME/MeetingInbox"                     # new audio lands here (drop your own files here too)
INBOX_DONE="$HOME/MeetingInbox-processed"      # audio after transcription (the app plays it from here)
TRANSCRIPTS="$HOME/MeetingTranscripts"         # transcripts waiting to be summarized
TRANSCRIPTS_DONE="$HOME/MeetingTranscripts-processed"
TRANSCRIPTS_FAILED="$HOME/MeetingTranscripts-failed"
STATE="$HOME/.meeting-notes"                   # config, prompt, context files, locks, logs

# --- Tools (install.sh fills these in from your machine) -------------------------------------
CLAUDE_BIN="__CLAUDE_BIN__"                    # Claude Code CLI
NODE_BIN_DIR="__NODE_BIN_DIR__"                # folder holding node, claude and plaud
PYTHON_BIN="__PYTHON_BIN__"                    # python3 (3.9+, standard library only)
MW_BIN="__MW_BIN__"                            # MacWhisper CLI
FFMPEG_BIN="__FFMPEG_BIN__"
PANDOC_BIN="__PANDOC_BIN__"                    # only needed if EMAIL_DIR is set

# --- Pipeline options ------------------------------------------------------------------------
DENOISE=1          # 1 = clean up the audio with ffmpeg before transcribing
REDIARIZE=1        # 1 = re-split speakers with pyannote (needs pipeline/setup-pyannote.sh; skipped if missing)
PULL_DAYS=3        # how far back plaud-pull looks for new recordings
KEEP_AUDIO_DAYS=180
KEEP_TRANSCRIPT_DAYS=60

# --- Apple Reminders (reminders/) ------------------------------------------------------------
REMINDERS=0                         # 1 = push your to-dos to Apple Reminders and sync ticks both ways
REMINDERS_LIST="Meeting Actions"    # the Reminders list to use (created if missing)
REMINDERS_DELEGATE=1                # 1 = also push "To Delegate" items, prefixed "[Delegate] "

# --- Notes app (app/) ------------------------------------------------------------------------
APP_PORT=8787                       # the app listens on 127.0.0.1 only; see app/README.md for phone access

# --- Extras (extras/) ------------------------------------------------------------------------
LOCAL_MODEL=""                      # e.g. "qwen2.5:3b": if Claude fails 3x, write a draft with this Ollama model
OLLAMA_BIN="/opt/homebrew/bin/ollama"
NTFY_TOPIC=""                       # health-check alerts to your phone via ntfy.sh (pick a long random topic)
