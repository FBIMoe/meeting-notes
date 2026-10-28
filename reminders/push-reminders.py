#!/usr/bin/env python3
"""push-reminders.py <note.md> — send a note's open to-dos to Apple Reminders.

Pushes the unchecked boxes under "## My Action Items" (and "## To Delegate", prefixed "[Delegate] ",
unless REMINDERS_DELEGATE=0). Each reminder's notes field says which meeting it came from. Nothing is
pushed twice. "What Others Are Working On" is never pushed — those aren't your tasks.
summarize.sh runs this for every new note when REMINDERS=1.

  push-reminders.py --test   create (and then delete) a test reminder, to trigger the macOS permission prompt
"""
import os, sys
import remlib as R

if len(sys.argv) < 2:
    print(__doc__.strip(), file=sys.stderr); sys.exit(2)

if sys.argv[1] == "--test":
    R.osascript("add_reminder.applescript", R.LIST, "meeting-notes test (safe to delete)", "permission check")
    R.osascript("delete_reminder.applescript", R.LIST, "meeting-notes test (safe to delete)")
    print(f"OK — this Mac can create reminders in '{R.LIST}'.")
    sys.exit(0)

path = sys.argv[1]
text = open(path, encoding="utf-8", errors="replace").read()
title = R.note_title(text, path)
state = R.load_state()
added = 0
for _, name, ticked in R.checkboxes(text):
    k = R.key(text, path, name)
    if ticked or k in state["pushed"]:
        continue
    R.osascript("add_reminder.applescript", R.LIST, name, title)
    state["pushed"][k] = {"note": os.path.basename(path), "name": name, "done": False}
    R.save_state(state)                       # after each one, so a failure halfway never duplicates
    added += 1
print(f"pushed {added} reminder(s) to '{R.LIST}' from: {title}")
