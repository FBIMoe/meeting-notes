"""remlib.py — shared helpers for the Apple Reminders sync (push-reminders.py, sync-reminders.py).

State lives in $STATE/reminders.json:
  {"pushed": {key: {"note": <note file name>, "name": <reminder text>, "done": bool}},
   "synced": [<ids of completed reminders already copied into notes>]}
key = sha1(recording name + "|" + reminder text), so the same task is never pushed twice — even when
a re-run gives the note a new file name. (Notes without a `recording:` line use their file name.)

Set MEETING_NOTES_DRY_RUN=1 to print what would happen instead of touching Reminders.
"""
import os, re, sys, json, glob, hashlib, subprocess

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
import mnconfig

C = mnconfig.load()
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(C["STATE"], "reminders.json")
LIST = C.get("REMINDERS_LIST") or "Meeting Actions"
DRY = os.environ.get("MEETING_NOTES_DRY_RUN") == "1"
SECTIONS = [("My Action Items", "")] + ([("To Delegate", "[Delegate] ")] if C.get("REMINDERS_DELEGATE", "1") == "1" else [])
CHECK = re.compile(r'^(\s*-\s*)\[([ xX])\](\s*)(.+?)\s*$')


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            s = json.load(f)
    except Exception:
        s = {}
    s.setdefault("pushed", {}); s.setdefault("synced", [])
    return s


def save_state(s):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_FILE)


def clean(text):
    """Checkbox text → reminder text: no [[links]], **bold** or `code`."""
    text = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', text)
    text = re.sub(r'\[\[|\]\]|\*\*|`', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def norm(text):
    """For matching a reminder back to its checkbox: case, prefix and trailing period don't matter."""
    text = re.sub(r'^\[Delegate\]\s*', '', clean(text))
    return text.lower().rstrip('.')


def ident(text, path):
    m = re.search(r'^recording:\s*(.+)$', text, re.M)
    return m.group(1).strip().strip('"\'') if m else os.path.basename(path)


def key(text, path, name):
    return hashlib.sha1((ident(text, path) + "|" + name).encode()).hexdigest()


def note_title(text, path):
    m = re.search(r'^title:\s*(.+)$', text, re.M) or re.search(r'^#\s+(.+)$', text, re.M)
    return m.group(1).strip().strip('"\'') if m else os.path.splitext(os.path.basename(path))[0]


def checkboxes(text):
    """[(line index, reminder name, ticked)] for the checkboxes in the synced sections."""
    lines, out, prefix = text.split("\n"), [], None
    for i, ln in enumerate(lines):
        if ln.startswith("## "):
            prefix = next((p for h, p in SECTIONS if ln[3:].strip().lower() == h.lower()), None)
            continue
        if prefix is None:
            continue
        m = CHECK.match(ln)
        if m:
            name = clean(m.group(4))
            if name:
                out.append((i, prefix + name, m.group(2) != " "))
    return out


def all_notes():
    return [f for f in glob.glob(os.path.join(C["NOTES_DIR"], "**", "*.md"), recursive=True)]


def osascript(script, *args, timeout=30):
    """Run one of the AppleScripts in this folder. Returns stdout; raises on failure."""
    if DRY:
        print(f"[dry run] {script} {' | '.join(args)}")
        return "1"
    try:
        r = subprocess.run(["osascript", os.path.join(HERE, script), *args],
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise SystemExit("Reminders didn't answer. It's probably waiting for the macOS permission prompt: "
                         "run `reminders/push-reminders.py --test` once from Terminal and click OK, or allow it "
                         "in System Settings > Privacy & Security > Automation.")
    if r.returncode != 0:
        raise SystemExit(f"Reminders error: {r.stderr.strip()}")
    return r.stdout
