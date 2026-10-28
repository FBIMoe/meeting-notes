# meeting-notes

Record a meeting on a Plaud (or any recorder). A few minutes later, a clean, organized Markdown note shows up in your notes folder. It lists who was there, what was decided, **your** to-dos kept separate from everyone else's, open questions, and a mind map. Optionally your to-dos land in Apple Reminders, and you get a phone app that leads with the TL;DR.

It runs unattended on a Mac. Transcription and speaker separation happen on your Mac. Only the transcript text goes to Claude.

<p align="center">
  <img src="docs/app-home.png" width="270" alt="App home screen: your to-dos across meetings">
  &nbsp;&nbsp;
  <img src="docs/app-meeting.png" width="270" alt="A meeting in the app: the point, what matters, your to-dos">
</p>

*Screenshots use the fictional sample meeting in [`examples/`](examples/).*

```
Plaud cloud ─▶ audio ─▶ transcript ─────────────▶ Markdown note ─▶ Apple Reminders (optional)
             plaud-pull   transcribe               summarize      └▶ phone app (optional)
                          (denoise → MacWhisper    (Claude Code + your
                           → pyannote speakers)     people & vocabulary)
```

## What you get

- **A note that's actually organized.** Each recording is classified (meeting, training, idea, personal…) and gets a layout that fits it. A 1:1 doesn't look like a vendor presentation.
- **Your to-dos, and only yours.** Something counts as your task only if you said you'd do it, or were asked and agreed. Other people's commitments go under "What Others Are Working On". Tasks nobody took go under "To Delegate". Trainings and presentations don't produce fake to-dos.
- **Honesty about uncertainty.** Big rooms are organized by topic, and a speaker is named only when the words prove who it was. Doubts are collected in one "Unclear in the Recording" section instead of guesses scattered through the note.
- **Fixes that stick.** Tell it "Speaker 3 is Dana", and the note is rewritten. The correction is saved, so it still applies if the note is ever redone.
- **It's yours to tune.** It learns your world from three short files: who you are, the people in your meetings, and your jargon (and how Whisper mangles it).
- **Optional extras:**
  - Two-way Apple Reminders sync
  - A phone/iPad app, with TL;DR cards, to-dos, a "waiting on others" list, search, Ask, audio playback, and photo uploads
  - A health check that pings your phone only when something breaks
  - A local-model fallback for when Claude is down

## The parts

Everything except the core pipeline is optional. `install.sh` asks which parts you want, so you can take only what you need.

| Folder | What it is | Needs |
|---|---|---|
| [`pipeline/`](pipeline/) | **Core.** Download from Plaud → transcribe → summarize → file the note. Plus `rerun.sh` to redo a note. | MacWhisper Pro, Claude Code |
| [`prompts/`](prompts/) | The instructions Claude follows. Read it, change it. | — |
| [`reminders/`](reminders/) | Pushes your to-dos to Apple Reminders. Ticks sync both ways: complete a reminder and the box ticks in the note, tick the box and the reminder completes. | macOS Reminders |
| [`app/`](app/) | The phone/iPad web app. Runs on your Mac; reach it from anywhere with Tailscale. | Python 3 (built in), Tailscale for phone access |
| [`extras/`](extras/) | Health check and alerts · local Ollama fallback · on-device photo text reading (used by the app) | Ollama (for the fallback only) |
| [`examples/`](examples/) | A fictional starter kit: context files, a correction, a sample transcript and the exact note it produced. | — |

## What it costs

| | Cost |
|---|---|
| [MacWhisper Pro](https://goodsnooze.gumroad.com/l/macwhisper) | One-time purchase. Pro includes the `mw` command-line tool this uses. |
| [Claude](https://claude.ai) Pro or Max subscription | Monthly, and probably already paid if you use Claude Code. The scripts always unset `ANTHROPIC_API_KEY`, so you're never billed per token. |
| Plaud recorder | Optional. Any audio file you drop in the inbox works. The pipeline downloads the raw audio and transcribes it itself, so you don't need Plaud's transcription minutes. |
| Everything else | Free: ffmpeg, pandoc, pyannote, Ollama, Tailscale (personal plan), ntfy. |

## Requirements

- A Mac (Apple Silicon recommended), macOS 14 or later
- MacWhisper Pro with its command-line tool installed (MacWhisper → Settings), using the Large v3 Turbo model
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code), logged in with your Claude subscription (run `claude` once)
- `brew install ffmpeg pandoc` (pandoc is only needed for email copies)
- Optional:
  - the [Plaud CLI](https://www.npmjs.com/package/@plaud-ai/cli) (`npm install -g @plaud-ai/cli`, then `plaud login`) for automatic downloads
  - Python 3.12 or 3.13 for pyannote
  - Obsidian, or any Markdown app, to read the notes

## Quick start

```zsh
git clone https://github.com/FBIMoe/meeting-notes.git ~/meeting-notes
cd ~/meeting-notes
./install.sh                  # checks your tools, writes ~/.meeting-notes/, asks about each optional part
```

Then:

1. **Set where notes go.** Edit `~/.meeting-notes/config.sh` and set at least `NOTES_DIR`, for example a folder in your Obsidian vault.
2. **Tell it about your world.** Replace the example files in `~/.meeting-notes/context/` with your own. They start as the fictional examples, so you can see the format.
   - `about-me.md`: who you are, your role, your boss, what you record.
   - `people.md`: the people in your meetings, with roles and nicknames. Mark yourself with `— me;`.
   - `vocabulary.md`: your jargon, product names and systems, plus how Whisper mishears them.
3. **Get better speaker separation (recommended):** run `pipeline/setup-pyannote.sh`. It needs a free Hugging Face account; the script explains.
4. **Record something.** Or drop any audio file into `~/MeetingInbox` to try it without a Plaud. A note appears a few minutes later.

Everything personal lives in `~/.meeting-notes/`, outside this repo. You can `git pull` updates without touching your files.

## Fixing a note

Don't edit the note itself. Tell the pipeline instead, so the fix sticks:

```zsh
# the file name is the recording name (also in the note's frontmatter as `recording:`)
cat >> ~/.meeting-notes/meeting-hints/"2026-01-12_Monday team meeting.txt" <<'EOF'
- Speaker 3 is Dana Okafor (Safety Coordinator). She was PRESENT.
- "Rob" was mentioned but was NOT there.
EOF
pipeline/rerun.sh "2026-01-12_Monday team meeting" "/path/to/the/old note.md"
```

In the app, **Fix this note** does the same from your phone. If the person shows up in other meetings too, add them to `people.md` as well.

Changed the prompt or your context files? `rerun.sh` regenerates any note. Changed the transcription settings? Add `--audio` to re-transcribe from the original audio.

## Privacy: what leaves your Mac

- **Stays on your Mac:** audio, transcription, speaker separation, the app and its data, photos you add, and the text read from them.
- **Goes to Anthropic (via Claude Code):** the transcript text and your context files, to write the note. The app also sends a note's text to make its TL;DR card, and sends your notes when you use Ask. This is the same as pasting them into Claude.
- **Goes to iCloud, only if you choose:** if `NOTES_DIR` or `EMAIL_DIR` is in iCloud Drive, or Reminders is on, those sync like any of your files.
- **Never:** nothing is published, and the app isn't reachable from the internet (see [`app/README.md`](app/README.md)).
- **Private notes:** interviews, HR conversations and talks about your own job or pay are marked `private: true`. They never get an email copy.

## Running it without Claude

The summary step is one command: prompt + transcript in, Markdown note out. Set `LOCAL_MODEL` in `config.sh`, and when Claude fails three times, [`extras/local-draft.sh`](extras/) writes a clearly-flagged draft with Ollama instead. Pointing `summarize.sh` at Ollama full-time is a small change. Expect noticeably weaker results on the hard parts (who said what, who owns which task), especially from small models.

## Honest limits

- **One mic in a room of 10, plus a Zoom call, is still hard.** pyannote gets the *number* of speakers roughly right, but quiet or remote voices get merged. Big-room mode exists so the note stays truthful anyway.
- **macOS + MacWhisper only, as written.** For other platforms, swap `whisper.cpp` or faster-whisper in for `mw` in `transcribe.sh`; that's the main change.
- **Reminders sync matches by text.** If you rename a reminder, it can't find its checkbox anymore.

## Troubleshooting

- **Logs:** `~/Library/Logs/meeting-notes/` and `~/.meeting-notes/*-errors.log`
- **Run a step by hand:** `pipeline/transcribe.sh`, `pipeline/summarize.sh`
- **Kick a background job:** `launchctl kickstart -k gui/$(id -u)/com.meetingnotes.summarize`
- **Duplicate or "wall of text" transcripts?** Turn OFF MacWhisper's own watch folder and auto-export, because this pipeline drives `mw` itself. Check the live setting with `defaults read com.goodsnooze.MacWhisper`. That command shows what MacWhisper is actually using, which can differ from the plist file on disk.
- **Reminders didn't show up?** Run `reminders/push-reminders.py --test` from Terminal and click OK on the permission prompt. Also check System Settings › Privacy & Security › Automation.
- **Plaud login expired?** Run `plaud login`. The health check tells you when this happens.
- **Test everything without touching your setup:** `tests/smoke-test.sh` runs the whole flow in a throwaway folder, with stand-ins for Claude and MacWhisper.
- **Remove the background jobs:** `./install.sh --uninstall`

## License

MIT
