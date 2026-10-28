"""tldr.py — build the app's TL;DR card for each note (one small Claude call per note version).

The card is a sidecar JSON under ~/.meeting-notes/app/tldr/<note id>.json, keyed by the note's
content hash (checkbox state ignored), so the note itself is never touched. Uses Claude Code on your
Claude subscription — ANTHROPIC_API_KEY is always removed from the environment.
"""
import os, re, json, threading, subprocess, time
import notes as N
import mnconfig

CLAUDE = N.C["CLAUDE_BIN"]
TLDR_DIR = os.path.join(N.APPDIR, "tldr")
LOG = os.path.join(N.APPDIR, "tldr.log")
MAX_TRANSCRIPT = 160_000

PROMPT = """You turn a finished meeting note into a short TL;DR card. The reader is the person who recorded the meeting (the note calls them "you"/"the user"; they are the first person in the roster). They read it on a phone and want only what matters.

Use ONLY facts that are in the note. Never add, guess or embellish. Write plainly, in short sentences, with no emoji.

Return ONLY one JSON object — no prose, no code fence — with exactly these keys:
{
  "point": "ONE sentence, at most ~30 words: what this was and the outcome that matters most.",
  "matters": [ {"text": "...", "at": "MM:SS or H:MM:SS, or null"} ],
  "waiting": [ {"who": "...", "what": "...", "due": "short date like Oct 30, or null"} ],
  "todo_at": [ "MM:SS or null", ... ]
}

Rules:
- "matters": 3 to 5 items (1 to 3 for a very short recording): the decisions, changes, dates, numbers and problems that affect the reader. Start each "text" with its key phrase wrapped in **double asterisks**, then a short plain explanation. At most ~25 words each. Don't repeat the reader's own to-dos here.
- "at": the transcript timestamp where that point is discussed. Use the [timestamp] at the start of the transcript line. null if there is no transcript or you can't tell.
- "waiting": up to 5 things OTHER people said they would do that the reader may need to follow up on (from "What Others Are Working On", commitments, promises). Only real commitments with an owner — not general updates. "who" = the person's name as the note writes it (without [[ ]]). Empty list if none.
- "todo_at": one entry per numbered item under MY TO-DOS, same order and same count: the transcript timestamp where it came up, or null. Empty list if there are no to-dos.
- For a private interview or HR conversation, keep it factual and neutral.
"""


def card_path(nid):
    return os.path.join(TLDR_DIR, nid + ".json")


def get(note):
    """(card or None, is_current)."""
    d = N.load_json(card_path(note["id"]), None)
    if not d:
        return None, False
    return d.get("card"), d.get("key") == note["key"]


def _log(msg):
    os.makedirs(N.APPDIR, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%F %T ") + msg + "\n")


def _transcript_text(rec):
    blocks = N.transcript_blocks(os.path.join(N.TXT_DONE, rec + ".txt")) if rec else []
    out, last = [], None
    for spk, t, text in blocks:
        if spk == last and out:
            out[-1] += " " + text
        else:
            out.append(f"[{N.fmt_ts(t)}] {spk}: {text}")
        last = spk
    s = "\n".join(out)
    return s[:MAX_TRANSCRIPT]


def _parse(out, n_todos):
    s = out.strip()
    s = re.sub(r'^```(?:json)?\s*|\s*```$', '', s)
    a, b = s.find("{"), s.rfind("}")
    d = json.loads(s[a:b + 1])
    ts = lambda v: v if isinstance(v, str) and N.TS_RE.match(v.strip()) else None
    card = {
        "point": str(d.get("point", "")).strip(),
        "matters": [{"text": str(m.get("text", "")).strip(), "at": ts(m.get("at"))}
                    for m in d.get("matters", []) if isinstance(m, dict) and m.get("text")][:5],
        "waiting": [{"who": str(w.get("who", "")).strip(), "what": str(w.get("what", "")).strip(),
                     "due": (str(w["due"]).strip() if w.get("due") else None)}
                    for w in d.get("waiting", []) if isinstance(w, dict) and w.get("what")][:5],
        "todo_at": [ts(x) for x in (d.get("todo_at") or [])][:n_todos],
    }
    card["todo_at"] += [None] * (n_todos - len(card["todo_at"]))
    if not card["point"]:
        raise ValueError("no point")
    return card


def build(note):
    mine = [t for t in note["todos"]]
    todo_list = "\n".join(f"{i}. {t['text']}" for i, t in enumerate(mine, 1)) or "(none)"
    roster = ""
    if os.path.exists(N.PEOPLE_MD):
        roster = "\n".join(l for l in open(N.PEOPLE_MD, encoding="utf-8").read().splitlines() if l.startswith("- "))
    body = re.sub(r'## Mind Map.*', '', note["body"], flags=re.S)
    tr = _transcript_text(note["recording"])
    prompt = (PROMPT + "\n\nROSTER:\n" + roster + "\n\nNOTE:\n" + body + "\n\nMY TO-DOS:\n" + todo_list +
              "\n\nTRANSCRIPT:\n" + (tr or "(not available)"))
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)                 # bill your subscription, never the API
    env["PATH"] = mnconfig.path_env()
    r = subprocess.run([CLAUDE, "-p"], input=prompt, capture_output=True, text=True,
                       timeout=420, env=env, cwd=N.APPDIR)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"claude exit {r.returncode}: {r.stderr.strip()[:200]}")
    card = _parse(r.stdout, len(mine))
    N.save_json(card_path(note["id"]), {"key": note["key"], "title": note["title"], "card": card,
                                        "built": time.strftime("%F %T")})
    return card


class Worker(threading.Thread):
    """Background thread: keeps every note's card current, newest notes first."""
    def __init__(self, get_notes):
        super().__init__(daemon=True)
        self.get_notes = get_notes
        self.wake = threading.Event()
        self.failures = {}                             # note id -> (key, count)
        self.busy = None

    def run(self):
        while True:
            try:
                for n in self.get_notes():
                    card, current = get(n)
                    if current:
                        continue
                    k, c = self.failures.get(n["id"], (None, 0))
                    if k == n["key"] and c >= 3:
                        continue                       # give up on this version after 3 tries
                    self.busy = n["id"]
                    try:
                        build(n)
                        _log(f"built {n['base']}")
                        self.failures.pop(n["id"], None)
                    except Exception as e:
                        self.failures[n["id"]] = (n["key"], (c + 1) if k == n["key"] else 1)
                        _log(f"FAILED {n['base']}: {e}")
                    finally:
                        self.busy = None
            except Exception as e:
                _log(f"worker error: {e}")
            self.wake.wait(60)
            self.wake.clear()
