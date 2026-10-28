"""mnconfig.py — read ~/.meeting-notes/config.sh from Python.

The config is a zsh file (so it can use $HOME etc.), so we let zsh evaluate it and print the values.
Usage:  import mnconfig; C = mnconfig.load(); C["NOTES_DIR"]
"""
import os, subprocess

KEYS = ("NOTES_DIR EMAIL_DIR INBOX INBOX_DONE TRANSCRIPTS TRANSCRIPTS_DONE TRANSCRIPTS_FAILED STATE "
        "CLAUDE_BIN NODE_BIN_DIR PYTHON_BIN FFMPEG_BIN REMINDERS REMINDERS_LIST REMINDERS_DELEGATE "
        "APP_PORT LOCAL_MODEL OLLAMA_BIN NTFY_TOPIC KEEP_TRANSCRIPT_DAYS").split()

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_cache = None


def config_path():
    return os.environ.get("MEETING_NOTES_CONFIG", os.path.expanduser("~/.meeting-notes/config.sh"))


def load():
    global _cache
    if _cache is None:
        path = config_path()
        if not os.path.exists(path):
            raise SystemExit(f"meeting-notes: no config at {path} — run install.sh first")
        script = 'source "$1"; shift; for v in "$@"; do print -r -- "$v=${(P)v}"; done'
        out = subprocess.run(["/bin/zsh", "-c", script, "_", path, *KEYS],
                             capture_output=True, text=True, check=True).stdout
        _cache = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    return _cache


def path_env():
    """PATH for child processes (claude needs node on PATH)."""
    c = load()
    return ":".join(p for p in (c.get("NODE_BIN_DIR"), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin") if p)
