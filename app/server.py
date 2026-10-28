#!/usr/bin/env python3
"""server.py — the Meeting Notes app: a phone/iPad web app for reading and acting on your meeting notes.

Runs on your Mac as the launchd job com.meetingnotes.app, listening on 127.0.0.1 only.
`tailscale serve` puts it on your tailnet over HTTPS; nothing is reachable from the LAN or the internet.
Python standard library only.
"""
import base64
import os, re, sys, json, time, glob, datetime, mimetypes
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notes as N
import tldr
import actions as A

PORT = int(os.environ.get("APP_PORT") or N.C.get("APP_PORT") or 8787)
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
HOME = N.HOME
WAIT_DAYS = 21

worker = tldr.Worker(N.all_notes)


# ------------------------------------------------------------------ data assembly
def people_index(roster):
    """Name -> list of lowercase words that identify the person in free text."""
    idx = {}
    for p in roster:
        keys = {p["name"].lower(), p["short"].lower()} | {a.lower() for a in p["aliases"]}
        idx[p["name"]] = [k for k in keys if len(k) > 2]
    return idx


def mentions(text, keys):
    t = " " + N.plain(text).lower() + " "
    return any(re.search(r'(?<![a-z])' + re.escape(k) + r'(?![a-z])', t) for k in keys)


def meeting_people(n, roster):
    out = []
    for raw in n["people"]:
        m = N.match_person(raw, roster)
        if m and any(p["me"] and p["name"] == m for p in roster):
            continue                                    # the user themself
        name = m or re.split(r'\s*[,(]', N.plain(raw))[0].strip()
        if name and all(x["name"] != name for x in out):
            out.append({"name": name, "known": bool(m)})
    return out


def build_data():
    notes = N.all_notes()
    roster = N.roster()
    me = next((p for p in roster if p["me"]), None)
    others = [p for p in roster if not p["me"]]
    pidx = people_index(others)
    done = A.done_set()
    dismissed = N.load_json(A.DISMISSED, {})
    pend = A.settle_pending(notes)
    today = N.today()

    def age(d):
        try:
            return (today - datetime.date.fromisoformat(d[:10])).days
        except Exception:
            return 999

    meetings, todos, waiting = [], [], []
    for n in notes:
        card, current = tldr.get(n)
        tds = []
        for i, t in enumerate(n["todos"]):
            at = card["todo_at"][i] if card and current and i < len(card.get("todo_at", [])) else None
            tds.append({"id": t["id"], "text": t["text"], "kind": t["kind"], "at": at,
                        "done": t["done"] or t["id"] in done, "meeting": n["id"]})
        w = []
        for x in (card or {}).get("waiting", []):
            key = N.sid(n["id"] + "|" + x["who"] + "|" + x["what"])
            who = N.match_person(x["who"], others)
            w.append({"key": key, "who": who or x["who"], "known": bool(who), "what": x["what"],
                      "due": x.get("due"), "meeting": n["id"], "handled": key in dismissed})
        m = {k: n[k] for k in ("id", "title", "date", "category", "type", "format", "room", "private",
                               "minutes", "summary", "has_audio", "recording")}
        m.update(people=meeting_people(n, roster), todos=tds, waiting=w, tldr=card,
                 tldr_state="ready" if card and current else ("updating" if card else "making"),
                 age=age(n["date"]))
        tm = re.search(r'\d{4}-\d\d-\d\d (\d\d) (\d\d)', n["recording"] or "")
        m["time"] = datetime.time(int(tm.group(1)), int(tm.group(2))).strftime("%-I:%M %p") if tm else None
        m["photos"] = A.photo_list(n["recording"])
        m.pop("recording")
        meetings.append(m)
        todos += [t for t in tds if t["kind"] in ("mine", "delegate")]
        if age(n["date"]) <= WAIT_DAYS:
            waiting += [x for x in w if not x["handled"]]

    people = []
    for p in others:
        keys = pidx[p["name"]]
        met = [m for m in meetings if any(x["name"] == p["name"] for x in m["people"])]
        owe_me = [x for x in waiting if x["who"] == p["name"]]
        i_owe = [t for t in todos if not t["done"] and mentions(t["text"], keys)]
        bring = []
        for m in met:
            n = next(x for x in notes if x["id"] == m["id"])
            for h, t in n["sections"]:
                if h.lower().startswith("bring up"):
                    bring += [{"text": N.plain(l.lstrip("-* ").strip()), "meeting": m["id"]}
                              for l in t.splitlines() if l.strip().startswith(("-", "*"))]
        if not (met or owe_me or i_owe):
            continue
        people.append({"name": p["name"], "short": p["short"], "role": p["role"], "group": p["group"],
                       "last": met[0]["date"] if met else None, "meetings": [m["id"] for m in met],
                       "theyOwe": owe_me, "youOwe": [t["id"] for t in i_owe], "bring": bring[:6]})
    people.sort(key=lambda p: (p["last"] or ""), reverse=True)

    return {"me": {"name": me["name"] if me else "", "first": me["short"] if me else ""},
            "today": today.isoformat(), "meetings": meetings, "todos": todos, "waiting": waiting,
            "people": people, "roster": [{"name": p["name"], "short": p["short"]} for p in others],
            "pending": [dict(v, recording=k) for k, v in pend.items()],
            "processing": processing(), "health": health(notes), "reminders": A.REMINDERS,
            "generated": time.time()}


def _rec_label(name):
    m = re.search(r'(\d{4})-(\d\d)-(\d\d) (\d\d) (\d\d)', name)
    if not m:
        return os.path.splitext(name)[0]
    d = datetime.datetime(*map(int, m.groups()))
    return d.strftime("%b %-d, %-I:%M %p")


def processing():
    out = []
    for f in glob.glob(os.path.join(N.C["INBOX"], "*")):
        if f.lower().endswith(N.AUDIO_EXT):
            out.append({"label": _rec_label(os.path.basename(f)), "stage": "Transcribing"})
    for f in glob.glob(os.path.join(N.C["TRANSCRIPTS"], "*.txt")):
        out.append({"label": _rec_label(os.path.basename(f)), "stage": "Writing the note"})
    return out


def health(notes):
    last = max((n["mtime"] for n in notes), default=0)
    failed = len(glob.glob(os.path.join(N.C["TRANSCRIPTS_FAILED"], "*.txt")))
    return {"last_note": last, "failed": failed, "cards_busy": bool(worker.busy)}


def meeting_detail(nid):
    n = next((x for x in N.all_notes() if x["id"] == nid), None)
    if not n:
        return None
    body = re.sub(r'\n## Mind Map.*', '', n["body"], flags=re.S)
    body = re.sub(r'^# .*\n', '', body, count=1)
    return {"id": n["id"], "body": body.strip()}


def search(q):
    q = q.strip().lower()
    if len(q) < 2:
        return []
    out = []
    for n in N.all_notes():
        body = re.sub(r'^#+\s.*$|^\s*[-*]\s*(\[[ xX]\]\s*)?|^```.*?^```', '', n["body"], flags=re.M | re.S)
        hay = N.plain(n["title"] + " — " + body)
        i = hay.lower().find(q)
        if i < 0:
            continue
        a = max(0, i - 60)
        out.append({"id": n["id"], "title": n["title"], "date": n["date"],
                    "snippet": ("…" if a else "") + hay[a:i + len(q) + 90] + "…"})
    return out[:30]


# ------------------------------------------------------------------ HTTP
class H(BaseHTTPRequestHandler):
    server_version = "MeetingNotes/1"

    def log_message(self, fmt, *args):
        pass

    def _host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        return host in ("127.0.0.1", "localhost") or host.endswith(".ts.net")   # blocks DNS rebinding

    def _send(self, code, body, ctype="application/json", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _file(self, path, ctype=None, cache="no-cache"):
        size = os.path.getsize(path)
        ctype = ctype or mimetypes.guess_type(path)[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        m = re.match(r'bytes=(\d*)-(\d*)', rng or "")
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1)); end = int(m.group(2)) if m.group(2) else size - 1
            else:
                start = max(0, size - int(m.group(2)))
            end = min(end, size - 1)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(65536, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "forbidden"})
        u = urlparse(self.path)
        p, qs = u.path, parse_qs(u.query)
        try:
            if p == "/api/data":
                return self._send(200, build_data())
            if p.startswith("/api/meeting/"):
                d = meeting_detail(p.rsplit("/", 1)[1])
                return self._send(200, d) if d else self._send(404, {"error": "That meeting is gone or being redone."})
            if p == "/api/search":
                return self._send(200, search(qs.get("q", [""])[0]))
            if p.startswith("/api/ask/"):
                j = A.JOBS.get(p.rsplit("/", 1)[1])
                return self._send(200, j) if j else self._send(404, {"error": "unknown question"})
            if p.startswith("/api/photo/"):
                _, _, _, nid, fname = (p.split("/") + ["", ""])[:5]
                n = next((x for x in N.all_notes() if x["id"] == nid), None)
                f = A.photo_path(n["recording"], fname) if n else None
                return self._file(f, "image/jpeg", "private, max-age=86400") if f and os.path.isfile(f) else self._send(404, {"error": "no photo"})
            if p.startswith("/api/audio/"):
                nid = p.rsplit("/", 1)[1].split(".")[0]
                n = next((x for x in N.all_notes() if x["id"] == nid), None)
                f = A.meeting_audio(n) if n else None
                return self._file(f, "audio/mp4") if f else self._send(404, {"error": "no audio"})
            # static app
            rel = unquote(p).lstrip("/") or "index.html"
            path = os.path.realpath(os.path.join(STATIC, rel))
            if not path.startswith(os.path.realpath(STATIC) + os.sep) or not os.path.isfile(path):
                path = os.path.join(STATIC, "index.html")          # client-side routes
            return self._file(path)
        except Exception as e:
            A.log(f"GET {p} failed: {e!r}")
            return self._send(500, {"error": "Something went wrong on the Mac."})

    def do_POST(self):
        if not self._host_ok() or self.headers.get("X-App") != "1":
            return self._send(403, {"error": "forbidden"})          # blocks cross-site form posts
        try:
            ln = int(self.headers.get("Content-Length") or 0)
            if ln > (40_000_000 if self.path == "/api/add" else 20000):
                return self._send(413, {"error": "too long"})
            body = json.loads(self.rfile.read(ln) or b"{}")
        except Exception:
            return self._send(400, {"error": "bad request"})
        p = urlparse(self.path).path
        try:
            notes = N.all_notes()
            find = lambda nid: next((x for x in notes if x["id"] == nid), None)
            if p == "/api/todo":
                for n in notes:
                    t = next((t for t in n["todos"] if t["id"] == body.get("id")), None)
                    if t:
                        A.set_todo(n, t, bool(body.get("done")))
                        return self._send(200, {"ok": True})
                return self._send(404, {"error": "That to-do changed. Pull down to refresh."})
            if p == "/api/waiting/handled":
                A.dismiss_waiting(str(body.get("key", ""))[:40])
                return self._send(200, {"ok": True})
            if p == "/api/fix":
                n = find(body.get("id"))
                if not n:
                    return self._send(404, {"error": "That meeting is already being redone."})
                A.fix(n, str(body.get("text", ""))[:4000])
                return self._send(200, {"ok": True})
            if p == "/api/add":
                n = find(body.get("id"))
                if not n:
                    return self._send(404, {"error": "That meeting is being redone. Try again in a few minutes."})
                imgs = []
                for u in (body.get("photos") or [])[:12]:
                    raw = base64.b64decode(str(u).split(",", 1)[-1], validate=False)
                    if raw[:3] != b"\xff\xd8\xff":
                        return self._send(400, {"error": "One of the photos couldn't be read."})
                    imgs.append(raw)
                return self._send(200, {"ok": True, **A.add_extras(n, str(body.get("text", ""))[:4000], imgs)})
            if p == "/api/delete":
                n = find(body.get("id"))
                if not n:
                    return self._send(404, {"error": "That meeting is already gone or being redone."})
                return self._send(200, {"ok": True, **A.delete_meeting(n)})
            if p == "/api/ask":
                q = str(body.get("q", "")).strip()[:500]
                if not q:
                    return self._send(400, {"error": "Type a question first."})
                return self._send(200, {"job": A.ask(q)})
            return self._send(404, {"error": "not found"})
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        except Exception as e:
            A.log(f"POST {p} failed: {e!r}")
            return self._send(500, {"error": str(e)[:200] or "Something went wrong on the Mac."})


def main():
    os.makedirs(N.APPDIR, exist_ok=True)
    os.chmod(N.APPDIR, 0o700)
    worker.start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    srv.daemon_threads = True
    print(f"Meeting Notes app on http://127.0.0.1:{PORT}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
