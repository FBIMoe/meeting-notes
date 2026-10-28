"""actions.py — the things the app's buttons do.

Everything that changes a meeting goes through the pipeline's own tools: a fix is a per-meeting
correction (meeting-hints/<recording>.txt) + pipeline/rerun.sh, so summarize.sh rewrites the note with
all its usual context. The app only edits a note in place to tick a to-do.
"""
import os, re, sys, json, glob, time, shutil, threading, subprocess
import notes as N
import mnconfig

C = N.C
HOME = N.HOME
REPO = mnconfig.REPO
RERUN = os.path.join(REPO, "pipeline", "rerun.sh")
HINTS = os.path.join(N.STATE, "meeting-hints")
PENDING = os.path.join(N.APPDIR, "pending.json")
DONE = os.path.join(N.APPDIR, "done.json")              # to-dos ticked here, by todo_key
DISMISSED = os.path.join(N.APPDIR, "dismissed.json")    # "waiting on" items marked handled
AUDIO = os.path.join(N.APPDIR, "audio")
FFMPEG = C.get("FFMPEG_BIN") or "ffmpeg"
PHOTOS = os.path.join(N.APPDIR, "photos")              # photos/<recording>/<stamp>-<n>.jpg — local only
OCR = os.path.join(REPO, "extras", "ocr-image")        # built from extras/ocr-image.swift by install.sh
PHOTO_RE = re.compile(r'^\d{8}-\d{6}-\d{1,2}\.jpg$')
TRASH = os.path.join(N.STATE, "deleted")
REMINDERS = C.get("REMINDERS") == "1"
LOCK = threading.Lock()


def log(msg):
    with open(os.path.join(N.APPDIR, "actions.log"), "a", encoding="utf-8") as f:
        f.write(time.strftime("%F %T ") + msg + "\n")


# ------------------------------------------------------------------ to-dos
def set_todo(note, todo, done):
    with LOCK:
        d = N.load_json(DONE, {})
        if done:
            d[todo["id"]] = time.time()
        else:
            d.pop(todo["id"], None)
        N.save_json(DONE, d)
        text = open(note["path"], encoding="utf-8").read()
        new_line = re.sub(r'\[[ xX]\]', "[x]" if done else "[ ]", todo["raw"], count=1)
        if todo["raw"] in text and new_line != todo["raw"]:
            with open(note["path"], "w", encoding="utf-8") as f:     # in place (keeps the file's owner)
                f.write(text.replace(todo["raw"], new_line, 1))
    if REMINDERS:
        threading.Thread(target=_reminder, args=(note, todo, done), daemon=True).start()


def _reminder(note, todo, done):
    """Complete (or reopen) the reminder push-reminders.py made for this to-do."""
    try:
        sys.path.insert(0, os.path.join(REPO, "reminders"))
        import remlib as R
        m = R.CHECK.match(todo["raw"])
        name = ("[Delegate] " if todo["kind"] == "delegate" else "") + R.clean(m.group(4) if m else todo["text"])
        with LOCK:
            state = R.load_state()
            item = state["pushed"].get(R.key(open(note["path"], encoding="utf-8").read(), note["path"], name))
            if not item:
                return                                  # never pushed (e.g. reminders were off then)
            n = R.osascript("set_reminder.applescript", R.LIST, name, "true" if done else "false").strip()
            item["done"] = done
            R.save_state(state)
        log(f"reminder {'done' if done else 'reopened'} ({n}): {name[:60]}")
    except BaseException as e:                          # remlib raises SystemExit on Reminders errors
        log(f"reminder update failed: {todo['text'][:60]}: {e}")


def done_set():
    return N.load_json(DONE, {})


def dismiss_waiting(key):
    with LOCK:
        d = N.load_json(DISMISSED, {})
        d[key] = time.time()
        N.save_json(DISMISSED, d)


# ------------------------------------------------------------------ fixes / re-runs
def pending():
    return N.load_json(PENDING, {})


def _mark_pending(note, why):
    with LOCK:
        p = pending()
        p[note["recording"]] = {"since": time.time(), "title": note["title"], "date": note["date"],
                                "why": why, "id": note["id"]}
        N.save_json(PENDING, p)


def settle_pending(notes):
    """Drop pending entries whose new note has landed (or that are over 40 minutes old)."""
    p = pending()
    if not p:
        return p
    by_rec = {n["recording"]: n for n in notes if n["recording"]}
    changed = False
    for rec, v in list(p.items()):
        n = by_rec.get(rec)
        if (n and n["mtime"] > v["since"]) or time.time() - v["since"] > 2400:
            p.pop(rec); changed = True
    if changed:
        with LOCK:
            N.save_json(PENDING, p)
    return p


def add_correction(rec, lines):
    os.makedirs(HINTS, mode=0o700, exist_ok=True)
    path = os.path.join(HINTS, rec + ".txt")
    with open(path, "a", encoding="utf-8") as f:
        for ln in lines:
            f.write(f"- ({time.strftime('%b %-d')}, from the app) {ln.strip()}\n")
    os.chmod(path, 0o600)


def rerun(note, why):
    if not note["recording"]:
        raise ValueError("This note isn't linked to its recording, so it can't be redone from the app.")
    if not any(os.path.exists(os.path.join(d, note["recording"] + ".txt"))
               for d in (N.TXT_DONE, C["TRANSCRIPTS_FAILED"])):
        raise ValueError(f"The transcript for this meeting is gone (transcripts are kept "
                         f"{C.get('KEEP_TRANSCRIPT_DAYS') or 60} days), so it can't be redone.")
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    r = subprocess.run(["/bin/zsh", RERUN, note["recording"], note["path"]], capture_output=True, text=True,
                       timeout=60, env=env)
    log(f"rerun ({why}) {note['recording']}: {r.returncode} {r.stdout.strip()} {r.stderr.strip()[:200]}")
    if r.returncode != 0:
        raise RuntimeError("The redo didn't start: " + (r.stdout.strip() or r.stderr.strip())[:200])
    _mark_pending(note, why)


def fix(note, text):
    text = text.strip()
    if not text:
        raise ValueError("Type what's wrong first.")
    add_correction(note["recording"], [text])
    rerun(note, "fix")


# ------------------------------------------------------------------ photos & own notes
def photo_list(rec):
    d = os.path.join(PHOTOS, rec or "")
    return sorted(f for f in os.listdir(d) if PHOTO_RE.match(f)) if rec and os.path.isdir(d) else []


def photo_path(rec, fname):
    return os.path.join(PHOTOS, rec, fname) if rec and PHOTO_RE.match(fname) else None


def add_extras(note, text, images):
    """Save photos (JPEG bytes) + read their text on-device, add both to this recording's corrections, redo the note."""
    text = text.strip()
    if not text and not images:
        raise ValueError("Add a photo or type a note first.")
    if not note["recording"]:
        raise ValueError("This note isn't linked to its recording, so it can't be redone from the app.")
    d = os.path.join(PHOTOS, note["recording"])
    os.makedirs(d, mode=0o700, exist_ok=True)
    os.chmod(PHOTOS, 0o700)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    lines = []
    if text:
        lines.append("My own notes from the meeting (typed by me, so names, numbers and spellings are reliable — "
                     "work them into the note where they fit): " + " ".join(text.split()))
    for i, img in enumerate(images, 1):
        path = os.path.join(d, f"{stamp}-{i}.jpg")
        with open(path, "wb") as f:
            f.write(img)
        os.chmod(path, 0o600)
        words = ""
        if os.access(OCR, os.X_OK):
            try:
                r = subprocess.run([OCR, path], capture_output=True, text=True, timeout=90)
                words = "\n".join(l.strip() for l in r.stdout.splitlines() if l.strip())
            except Exception as e:
                log(f"ocr failed {path}: {e!r}")
        else:
            log("ocr skipped: extras/ocr-image isn't built (re-run install.sh)")
        if words:
            lines.append(f"A photo I took during the meeting shows this text (read on-device by OCR; names and "
                         f"numbers on it are reliable, a few characters may be garbled — use what it shows where it "
                         f"fits, e.g. a whiteboard, slide, screen or handout):\n    " + words[:6000].replace("\n", "\n    "))
    log(f"extras {note['recording']}: text={bool(text)} photos={len(images)} read={len(lines) - bool(text)}")
    if lines:
        add_correction(note["recording"], lines)
        rerun(note, "photos")
        return {"redo": True, "read": len(lines) - bool(text)}
    return {"redo": False, "read": 0}


# ------------------------------------------------------------------ delete
def delete_meeting(note):
    """Move a meeting and everything made from it into ~/.meeting-notes/deleted/<note>/ (undo = move back)."""
    import tldr
    base, rec = os.path.basename(note["path"])[:-3], note["recording"]
    dest = os.path.join(TRASH, base)
    if os.path.exists(dest):
        dest += time.strftime("-%Y%m%d-%H%M%S")
    os.makedirs(dest, mode=0o700)
    moved = []

    def take(src, sub=""):
        if src and os.path.exists(src):
            d = os.path.join(dest, sub) if sub else dest
            os.makedirs(d, exist_ok=True)
            shutil.move(src, os.path.join(d, os.path.basename(src)))
            moved.append(sub or "note")
    take(note["path"])
    if C.get("EMAIL_DIR"):
        take(os.path.join(C["EMAIL_DIR"], base + ".txt"), "email copy")
    if rec:
        take(os.path.join(N.TXT_DONE, rec + ".txt"), "transcript")
        take(N.find_audio(rec), "audio")
        take(os.path.join(HINTS, rec + ".txt"), "corrections")
        take(os.path.join(PHOTOS, rec), "photos")
    for f in (tldr.card_path(note["id"]), os.path.join(AUDIO, note["id"] + ".m4a")):
        try:
            os.remove(f)
        except OSError:
            pass
    m = N.load_json(N.RECMAP, {})
    if m.pop(base, None) is not None:
        N.save_json(N.RECMAP, m)
    log(f"deleted {base} -> {dest}: {', '.join(moved)}")
    return {"archived": dest}


# ------------------------------------------------------------------ ask
JOBS = {}
MAX_ASK_CHARS = 400_000
ASK_PROMPT = """Answer the question using ONLY the meeting notes below. They are the user's own notes, newest first.
Be brief and plain: a few sentences or a short list. Name people and dates where it helps. If the notes
don't say, answer "The notes don't say." — never guess.
End with one final line exactly like this, listing the titles of the notes you used:
— sources: <title>; <title>

QUESTION: {q}

NOTES:
"""


def ask(q):
    jid = N.sid(q + str(time.time()))
    JOBS[jid] = {"q": q, "state": "running", "started": time.time()}

    def run():
        env = dict(os.environ)
        env.pop("ANTHROPIC_API_KEY", None)
        env["PATH"] = mnconfig.path_env()
        try:
            notes = N.all_notes()
            ctx, size = [], 0
            for n in notes:                              # newest first, until the budget is used
                chunk = f"\n=== {n['title']} ({n['date']}) ===\n{n['body']}\n"
                if size + len(chunk) > MAX_ASK_CHARS:
                    break
                ctx.append(chunk); size += len(chunk)
            r = subprocess.run([C["CLAUDE_BIN"], "-p"], input=ASK_PROMPT.format(q=q) + "".join(ctx),
                               capture_output=True, text=True, timeout=300, env=env, cwd=N.APPDIR)
            out = r.stdout.strip()
            if r.returncode != 0 or not out:
                raise RuntimeError(r.stderr.strip()[-200:] or "no answer")
            ans, _, src = out.rpartition("— sources:")
            if not ans:
                ans, src = out, ""
            hits = [n["title"] for n in notes if n["title"] and n["title"] in src]
            JOBS[jid].update(state="done", answer=ans.strip(), sources=hits)
        except Exception as e:
            log(f"ask failed: {e}")
            JOBS[jid].update(state="error", error="Couldn't get an answer right now. Try again in a minute.")
    threading.Thread(target=run, daemon=True).start()
    for k in [k for k, v in JOBS.items() if time.time() - v["started"] > 3600]:
        JOBS.pop(k, None)
    return jid


# ------------------------------------------------------------------ audio
def meeting_audio(note):
    """Whole recording as AAC .m4a (Safari-friendly, seekable), converted once and cached."""
    src = N.find_audio(note["recording"])
    if not src:
        return None
    os.makedirs(AUDIO, exist_ok=True)
    out = os.path.join(AUDIO, note["id"] + ".m4a")
    if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(src):
        os.utime(out)
        return out
    with LOCK:
        tmp = out + ".tmp.m4a"
        subprocess.run([FFMPEG, "-nostdin", "-v", "error", "-y", "-i", src, "-ac", "1", "-c:a", "aac",
                        "-b:a", "48k", "-movflags", "+faststart", tmp], timeout=600)
        if os.path.exists(tmp):
            os.replace(tmp, out)
    for f in glob.glob(os.path.join(AUDIO, "*.m4a")):          # keep the cache small
        if time.time() - os.path.getmtime(f) > 14 * 86400:
            os.remove(f)
    return out if os.path.exists(out) else None
