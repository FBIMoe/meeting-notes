#!/usr/bin/env python3
"""rediarize.py — re-label a MacWhisper transcript's speakers using pyannote community-1.

MacWhisper's built-in speaker labels are often wrong (one person split into several "speakers", or
two people merged). pyannote is far better at "who spoke when". We diarize the SAME audio MacWhisper
transcribed, give each transcript block to the pyannote speaker whose turn overlaps it most, and
rewrite the transcript in the exact same format (only the "Speaker N" values change).

MacWhisper transcript format (blank-line-separated blocks):
    Speaker 1          <- optional (absent in single-speaker dictations)
    00:12              <- MM:SS or HH:MM:SS start of the block
    <one or more text lines>

SAFETY: rewrites only when pyannote finds between --min-speakers and --max-speakers speakers.
Otherwise (or on any error) it exits non-zero and the caller keeps MacWhisper's original labels.

Usage: rediarize.py --transcript IN --audio AUDIO --out OUT [--min-speakers 2] [--max-speakers 12]
Run via the `rediarize` wrapper (pyannote venv).
"""
import sys, os, re, argparse, subprocess, tempfile

MODEL = "pyannote/speaker-diarization-community-1"
FFMPEG = os.environ.get("FFMPEG_BIN", "/opt/homebrew/bin/ffmpeg")
TS_RE = re.compile(r'^\d{1,2}:\d{2}(?::\d{2})?$')
SPK_RE = re.compile(r'^Speaker\s+\d+$', re.I)


def diarize(audio_path):
    """Returns [{'start','end','speaker'}] sorted by start."""
    import torch
    import soundfile as sf
    from pyannote.audio import Pipeline
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False); tmp.close()
    try:
        subprocess.run([FFMPEG, "-nostdin", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", tmp.name],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        wav, sr = sf.read(tmp.name, dtype="float32", always_2d=False)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    if wav.ndim > 1:
        wav = wav[:, 0]
    p = Pipeline.from_pretrained(MODEL)
    if torch.backends.mps.is_available():          # Apple-silicon GPU
        p.to(torch.device("mps"))
    res = p({"waveform": torch.from_numpy(wav).unsqueeze(0), "sample_rate": sr})
    ann = getattr(res, "speaker_diarization", res)
    ids, turns = {}, []
    for seg, _, label in ann.itertracks(yield_label=True):
        turns.append({"start": seg.start, "end": seg.end, "speaker": ids.setdefault(label, len(ids))})
    return sorted(turns, key=lambda t: t["start"])


def to_sec(ts):
    p = [int(x) for x in ts.split(":")]
    return p[0] * 60 + p[1] if len(p) == 2 else p[0] * 3600 + p[1] * 60 + p[2]


def parse_blocks(text):
    blocks = []
    for raw in re.split(r'\n\s*\n', text.strip("\n")):
        lines = raw.split("\n")
        i = 1 if lines and SPK_RE.match(lines[0].strip()) else 0
        if i < len(lines) and TS_RE.match(lines[i].strip()):
            ts = lines[i].strip()
            blocks.append({"raw": raw, "ts_sec": to_sec(ts), "ts_str": ts, "text_lines": lines[i + 1:], "parsed": True})
        else:
            blocks.append({"raw": raw, "parsed": False})
    return blocks


def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-speakers", type=int, default=2)
    ap.add_argument("--max-speakers", type=int, default=12)
    a = ap.parse_args()

    try:
        turns = diarize(a.audio)
    except Exception as e:
        sys.stderr.write(f"rediarize: diarization failed: {e}\n")
        return 4
    nspk = len({t["speaker"] for t in turns})
    if not turns or nspk < a.min_speakers or nspk > a.max_speakers:
        sys.stderr.write(f"rediarize: found {nspk} speaker(s) — keeping the original labels\n")
        return 20

    blocks = parse_blocks(open(a.transcript, encoding="utf-8", errors="replace").read())
    parsed = [b for b in blocks if b["parsed"]]
    audio_end = max(t["end"] for t in turns)
    for i, b in enumerate(parsed):           # a block runs until the next block starts
        b["start"] = b["ts_sec"]
        b["end"] = parsed[i + 1]["ts_sec"] if i + 1 < len(parsed) else audio_end
    for b in parsed:
        best, best_ov = None, 0.0
        for t in turns:
            ov = overlap(b["start"], b["end"], t["start"], t["end"])
            if ov > best_ov:
                best_ov, best = ov, t["speaker"]
        if best is None:                     # falls in a gap → nearest turn
            best = min(turns, key=lambda t: abs(t["start"] - b["start"]))["speaker"]
        b["speaker"] = best

    out = []
    for b in blocks:
        out.append("\n".join([f"Speaker {b['speaker'] + 1}", b["ts_str"]] + b["text_lines"]) if b["parsed"] else b["raw"])
    open(a.out, "w", encoding="utf-8").write("\n\n".join(out) + "\n")
    sys.stderr.write(f"rediarize: relabeled {len(parsed)} block(s) across {nspk} speaker(s)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
