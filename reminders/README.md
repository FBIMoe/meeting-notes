# reminders/: Apple Reminders, both ways

Turn it on with `./install.sh --with reminders`, or set `REMINDERS=1` in `config.sh` and re-run `./install.sh`.

## What happens

1. **A new note is filed.** `summarize.sh` runs `push-reminders.py`. Every unchecked box under `## My Action Items` becomes a reminder in your `REMINDERS_LIST` (default "Meeting Actions"). So does every box under `## To Delegate`, prefixed `[Delegate] `; turn that off with `REMINDERS_DELEGATE=0`. Each reminder's notes say `From meeting: <title>`. iCloud syncs the list to your iPhone and Watch.
2. **Every 15 minutes, `sync-reminders.py` runs:**
   - **Reminders → note:** a reminder you completed anywhere ticks the matching `- [ ]` → `- [x]` in its note.
   - **Note → Reminders:** a box you ticked in the note completes its reminder. That works in Obsidian, the app or any editor.
   - The app does this instantly when you tick something there, and un-ticking reopens the reminder.

## Which tasks are yours

This is decided by the prompt (`prompts/meeting-prompt.md`), not by this code. A task goes under My Action Items only when you said you'd do it, or were asked and agreed. Someone else's commitment goes under "What Others Are Working On", which is never pushed. Trainings and presentations get no checkboxes. When in doubt, the prompt leaves a task out: a missing to-do costs less than a fake one in your Reminders.

## No duplicates

Each pushed task is recorded in `~/.meeting-notes/reminders.json`, keyed by the recording name plus the task text. The same task is never pushed twice, even if the note is re-filed under a new name. Re-runs (`pipeline/rerun.sh`, or the app's Fix button) don't push at all.

## No due dates

Most meeting tasks don't have a real date, and made-up ones were just noise. If a date was said, it's in the task text ("…; by Friday (Jan 16)").

## Permissions

The first time it runs, macOS asks whether python3 / Terminal may control Reminders. Click **OK**. To trigger the prompt on purpose:

```zsh
reminders/push-reminders.py --test     # makes a test reminder and deletes it
```

If you missed the prompt, go to System Settings › Privacy & Security › Automation.

## Files

| File | Does |
|---|---|
| `push-reminders.py <note>` | Push one note's open to-dos. |
| `sync-reminders.py` | Both-way sync. Runs every 15 min as `com.meetingnotes.reminders`. |
| `remlib.py` | Shared parsing and state. `MEETING_NOTES_DRY_RUN=1` prints instead of touching Reminders. |
| `*.applescript` | The only code that talks to Reminders: add, list completed, complete or reopen, delete (used only by `--test`). |
