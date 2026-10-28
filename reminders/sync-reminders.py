#!/usr/bin/env python3
"""sync-reminders.py — keep note checkboxes and Apple Reminders in step, both ways. Runs every 15 min.

1. Reminders → notes: a reminder you completed (on your phone, watch, Mac) ticks its box in the note.
2. Notes → Reminders: a box you ticked in the note (in Obsidian, the app, any editor) completes its reminder.

Only items that push-reminders.py created are touched; nothing else in your Reminders is read or changed.
"""
import os, re
import remlib as R

state = R.load_state()
synced = set(state["synced"])
notes = R.all_notes()
texts = {}


def read(path):
    if path not in texts:
        texts[path] = open(path, encoding="utf-8", errors="replace").read()
    return texts[path]


# --- 1. Reminders → notes ----------------------------------------------------------------------
ticked = 0
by_title = {}
for p in notes:
    by_title.setdefault(R.note_title(read(p), p), []).append(p)
for row in R.osascript("list_completed.applescript", R.LIST).splitlines():
    parts = row.split("\t")
    if len(parts) < 2 or parts[0] in synced:
        continue
    rid, name, body = parts[0], parts[1], (parts[2] if len(parts) > 2 else "")
    title = re.sub(r'^From meeting:\s*', '', body).strip()
    want = R.norm(name)
    for p in by_title.get(title, []):
        lines = read(p).split("\n")
        hit = next((i for i, n, done in R.checkboxes(read(p)) if not done and R.norm(n) == want), None)
        if hit is None:
            continue
        lines[hit] = R.CHECK.sub(lambda m: f"{m.group(1)}[x]{m.group(3)}{m.group(4)}", lines[hit], count=1)
        texts[p] = "\n".join(lines)
        with open(p, "w", encoding="utf-8") as f:           # in place, so file ownership stays the same
            f.write(texts[p])
        k = R.key(texts[p], p, name)
        if k in state["pushed"]:
            state["pushed"][k]["done"] = True
        ticked += 1
        print(f"ticked in note: {name[:60]}  ({os.path.basename(p)})")
        break
    synced.add(rid)
state["synced"] = sorted(synced)
R.save_state(state)

# --- 2. Notes → Reminders ----------------------------------------------------------------------
completed = 0
for p in notes:
    for _, name, done in R.checkboxes(read(p)):
        k = R.key(read(p), p, name)
        item = state["pushed"].get(k)
        if done and item and not item["done"]:
            R.osascript("set_reminder.applescript", R.LIST, name, "true")
            item["done"] = True
            R.save_state(state)
            completed += 1
            print(f"completed reminder: {name[:60]}")

print(f"sync: {ticked} box(es) ticked from Reminders, {completed} reminder(s) completed from notes")
