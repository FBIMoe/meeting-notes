# extras/

## health-check.sh: alerts only when something breaks

`./install.sh --with health` runs this every 6 hours. It's quiet when everything is fine. When something is wrong, it sends a macOS notification. With `NTFY_TOPIC` set in `config.sh`, it also sends a push to your phone through [ntfy.sh](https://ntfy.sh): install the ntfy app, subscribe to a long random topic name, and put the same name in the config.

It checks:
- MacWhisper is running
- every background job is loaded
- nothing failed or has been waiting for more than 2 hours
- the Plaud login is still valid
- whether there are **new** error lines in `~/.meeting-notes/*-errors.log`

It remembers how far it read in each log, so an old error doesn't alert you again after every good run.

## local-draft.sh: when Claude is down

If Claude fails 3 times in a row and `LOCAL_MODEL` is set, `summarize.sh` calls this. It writes a clearly-flagged draft note into `Inbox/` using a local [Ollama](https://ollama.com) model, so a meeting is never lost. The transcript stays in the failed folder; `pipeline/rerun.sh` replaces the draft with a real note once Claude is back.

```zsh
brew install ollama && ollama pull qwen2.5:3b     # then LOCAL_MODEL="qwen2.5:3b" in config.sh
```

## ocr-image.swift: on-device text from photos

A small Apple Vision tool. The app uses it to read whiteboards, slides and handouts you add to a meeting. `install.sh` builds it, which needs the Xcode command line tools: `xcode-select --install`. To build it by hand:

```zsh
swiftc -O extras/ocr-image.swift -o extras/ocr-image
```
