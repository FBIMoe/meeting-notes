"""notes.py — read the meeting notes folder into plain dicts for the app.

Read-only on the notes. Each parse is cached by (mtime, size); a note that reads as 0 bytes (iCloud
Drive can briefly show a synced file as empty to background processes) keeps its last good parse
instead of vanishing.
"""
import os, re, sys, glob, json, hashlib, datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))
import mnconfig

C = mnconfig.load()
HOME = os.path.expanduser("~")
VAULT = C["NOTES_DIR"]
STATE = C["STATE"]
APPDIR = os.path.join(STATE, "app")
PEOPLE_MD = os.path.join(STATE, "context", "people.md")
TXT_DONE = C["TRANSCRIPTS_DONE"]
AUDIO_DONE = C["INBOX_DONE"]
AUDIO_EXT = (".ogg", ".m4a", ".mp3", ".wav")
RECMAP = os.path.join(APPDIR, "recordings.json")      # note basename -> recording name

_cache = {}      # path -> (mtime, size, parsed)


def sid(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ------------------------------------------------------------------ frontmatter / sections
def split_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    fm = {}
    for ln in text[3:end].splitlines():
        m = re.match(r'^([A-Za-z_]+):\s*(.*)$', ln)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm, text[end + 4:].lstrip("\n")


def fm_list(v):
    v = (v or "").strip()
    if v.startswith("["):
        v = v[1:-1] if v.endswith("]") else v[1:]
    items = re.findall(r'\s*(?:"((?:[^"\\]|\\.)*)"|([^,]+))', v)
    return [(a or b).replace('\\"', '"').strip().strip("'") for a, b in items if (a or b).strip()]


def fm_str(v):
    v = (v or "").strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v


def sections(body):
    """[(heading, text)] for each '## ' section; text before the first one is heading ''."""
    out, head, buf = [], "", []
    for ln in body.splitlines():
        if ln.startswith("# ") and not out and not buf:
            continue                                   # the H1 title
        if ln.startswith("## "):
            out.append((head, "\n".join(buf).strip()))
            head, buf = ln[3:].strip(), []
        else:
            buf.append(ln)
    out.append((head, "\n".join(buf).strip()))
    return [(h, t) for h, t in out if h or t]


def plain(s):
    s = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', s)
    s = re.sub(r'\[\[([^\]]+)\]\]', r'\1', s)
    return re.sub(r'\s+', ' ', s.replace("**", "").replace("`", "")).strip()


def todo_key(recording, text):
    return sid((recording or "") + "|" + plain(text).lower().rstrip("."))


def body_key(body):
    """Hash of the note content that ignores checkbox state (ticking a to-do isn't a new note)."""
    return sid(re.sub(r'- \[[xX ]\]', '- [ ]', body))


# ------------------------------------------------------------------ transcripts
TS_RE = re.compile(r'^(\d{1,2}:)?\d{1,2}:\d{2}$')


def to_secs(ts):
    p = [int(x) for x in ts.split(":")]
    return p[0] * 3600 + p[1] * 60 + p[2] if len(p) == 3 else p[0] * 60 + p[1]


def transcript_blocks(path):
    """[(speaker, seconds, text)] from a MacWhisper 'Speaker N / MM:SS / text' transcript."""
    if not path or not os.path.exists(path):
        return []
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    out, i = [], 0
    spk = "Speaker 1"                                   # one-speaker transcripts have no speaker lines
    while i < len(lines):
        head = None
        if i + 1 < len(lines) and TS_RE.match(lines[i + 1].strip()) and lines[i].strip() \
                and not TS_RE.match(lines[i].strip()):
            spk, head = lines[i].strip(), lines[i + 1].strip(); i += 2
        elif TS_RE.match(lines[i].strip()):
            head = lines[i].strip(); i += 1
        if head:
            t = to_secs(head)
            buf = []
            while i < len(lines) and lines[i].strip():
                buf.append(lines[i].strip())
                i += 1
            out.append((spk, t, " ".join(buf)))
        i += 1
    return out


def fmt_ts(sec):
    sec = int(sec)
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ------------------------------------------------------------------ notes
def find_audio(rec):
    """The recording's audio file in the processed-audio folder, or None."""
    for ext in AUDIO_EXT if rec else ():
        p = os.path.join(AUDIO_DONE, rec + ext)
        if os.path.exists(p):
            return p
    return None


def recording_map():
    return load_json(RECMAP, {})


def parse_note(path, recmap):
    st = os.stat(path)
    hit = _cache.get(path)
    if hit and hit[0] == st.st_mtime and hit[1] == st.st_size:
        return hit[2]
    text = open(path, encoding="utf-8", errors="replace").read()
    if not text.strip():
        return hit[2] if hit else None                 # iCloud lag: keep the last good read
    fm, body = split_frontmatter(text)
    rel = os.path.relpath(path, VAULT)
    base = os.path.basename(path)[:-3]
    rec = fm_str(fm.get("recording")) or recmap.get(base, "")
    secs = sections(body)
    todos = []
    for kind, head in (("mine", "My Action Items"), ("delegate", "To Delegate")):
        for h, t in secs:
            if h.lower() != head.lower():
                continue
            for ln in t.splitlines():
                m = re.match(r'^\s*-\s*\[([ xX])\]\s*(.+?)\s*$', ln)
                if m:
                    todos.append({"id": todo_key(rec or rel, m.group(2)), "text": plain(m.group(2)),
                                  "raw": ln, "done": m.group(1) != " ", "kind": kind})
    date = fm_str(fm.get("date")) or base[:10]
    title = fm_str(fm.get("title")) or base[11:]
    # fallback "point" until the TL;DR exists: the note's own summary paragraph
    first = next((t for h, t in secs if h.lower() in ("summary", "overview", "the idea", "what happened", "purpose")), "")
    blocks = transcript_blocks(os.path.join(TXT_DONE, rec + ".txt")) if rec else []
    n = {
        "id": sid(rec or rel), "path": path, "rel": rel, "base": base, "recording": rec,
        "title": title, "date": date, "category": fm.get("category", "") or rel.split(os.sep)[0],
        "type": fm.get("type", ""), "format": fm.get("format", ""), "room": fm.get("room", ""),
        "private": fm.get("private", "").lower() == "true" or "career" in fm.get("tags", ""),
        "tags": fm_list(fm.get("tags")), "people": fm_list(fm.get("people")),
        "minutes": round(blocks[-1][1] / 60) if blocks else None,
        "summary": plain(first.split("\n\n")[0])[:400],
        "todos": todos, "body": body, "sections": secs, "key": body_key(body),
        "mtime": st.st_mtime,
        "has_audio": bool(find_audio(rec)),
    }
    _cache[path] = (st.st_mtime, st.st_size, n)
    return n


def all_notes():
    recmap = recording_map()
    out, learned = [], False
    for f in glob.glob(os.path.join(VAULT, "**", "*.md"), recursive=True):
        rel = os.path.relpath(f, VAULT)
        if rel.split(os.sep)[0].startswith(("_", ".")) or os.sep not in rel:
            continue                                   # notes live in category folders; skip _System etc.
        try:
            n = parse_note(f, recmap)
        except OSError:
            continue
        if not n:
            continue
        if n["recording"] and recmap.get(n["base"]) != n["recording"]:
            recmap[n["base"]] = n["recording"]; learned = True
        out.append(n)
    if learned:
        save_json(RECMAP, recmap)                      # survives a re-render dropping the line
    out.sort(key=lambda n: (n["date"], n["mtime"]), reverse=True)
    return out


# ------------------------------------------------------------------ people
def roster():
    """[{name, short, aliases, role, group, me}] from people.md."""
    out, group = [], ""
    if not os.path.exists(PEOPLE_MD):
        return out
    for ln in open(PEOPLE_MD, encoding="utf-8", errors="replace"):
        ln = ln.rstrip("\n")
        g = re.match(r'^#\s*---\s*(.+?)\s*---', ln)
        if g:
            group = g.group(1); continue
        if not ln.startswith("- "):
            continue
        seg = ln[2:]
        name, role = (seg.split("—", 1) + [""])[:2] if "—" in seg else (seg, "")
        aliases = []
        am = re.search(r'\(also called:\s*([^)]*)\)', name)
        if am:
            aliases = [a.strip() for a in am.group(1).split(",") if a.strip()]
        name = re.sub(r'\(.*?\)', '', name).strip().strip('"')
        nick = re.search(r'"([^"]+)"', name)
        short = nick.group(1) if nick else name.split()[0]
        role = re.sub(r'\s*\[.*?\]\s*', ' ', role).strip()
        if name:
            out.append({"name": name, "short": short, "aliases": aliases, "role": role, "group": group,
                        "me": role.lower().startswith("you;") or role.lower().startswith("me;")})
    return out


def match_person(raw, people):
    """Best roster name for a free-text name ("Pree", "Mike Bell", "[[Priya Natarajan|Pree]]")."""
    s = plain(raw).lower().strip()
    if not s:
        return None
    for p in people:
        if s == p["name"].lower() or s in [a.lower() for a in p["aliases"]] or s == p["short"].lower():
            return p["name"]
    for p in people:
        if p["name"].lower() in s:
            return p["name"]
    return None


def today():
    return datetime.date.today()
