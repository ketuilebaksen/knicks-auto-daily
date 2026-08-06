#!/usr/bin/env python3
"""
assemble.py — build final video.

Hook (first section): Vox-style fast cuts from the b-roll library (work/broll/*)
with white-flash transitions, bold kinetic titles and whoosh SFX. Fast pacing.
Body: branded info cards (slow zoom) + every few paragraphs a b-roll interlude
with a lower-third. Different random scenes every day (seeded by date).
Falls back to cards-only if no b-roll exists.

Usage: python3 scripts/assemble.py content/current/script.json
"""
import datetime, glob, json, os, random, re, subprocess, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 24
FONT = os.path.join(BASE, "assets", "Anton-Regular.ttf")
CUT_LEN = 2.6          # target seconds per hook cut (fast)
BODY_BROLL_EVERY = 4   # every Nth body paragraph becomes a b-roll interlude

def run(cmd):
    subprocess.run(cmd, check=True)

def ffdur(path):
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0

def esc(text):
    text = re.sub(r"[^0-9A-Za-z ÇĞİÖŞÜçğıöşü'\-\.]", "", text)
    return text.replace("'", r"\'").replace(":", r"\:").upper()[:40]

class Broll:
    def __init__(self, rng):
        exts = ("*.mp4", "*.mov", "*.mkv", "*.webm", "*.m4v", "*.MP4", "*.MOV")
        files = []
        for e in exts:
            files += glob.glob(os.path.join(BASE, "work", "broll", "**", e), recursive=True)
        self.rng = rng
        self.clips = []
        for f in sorted(set(files)):
            d = ffdur(f)
            if d >= 3.0:
                self.clips.append((f, d))
        self.rng.shuffle(self.clips)
        self.i = 0
        print(f"[assemble] b-roll library: {len(self.clips)} clips")

    def any(self):
        return len(self.clips) > 0

    def pick(self, need):
        """Return (path, start) giving a fresh random window of `need` seconds."""
        f, d = self.clips[self.i % len(self.clips)]
        self.i += 1
        start = self.rng.uniform(0, max(0.0, d - need - 0.2))
        return f, start

def broll_cut(src, start, dur, out, title=None, flash=True, first_flash_only=False):
    vf = ["scale=1920:1080:force_original_aspect_ratio=increase",
          "crop=1920:1080", f"fps={FPS}"]
    if flash:
        vf.append("fade=t=in:st=0:d=0.14:color=white")
    if title:
        vf.append(
            f"drawtext=fontfile='{FONT}':text='{esc(title)}':"
            f"fontsize=86:fontcolor=white:x=90:y=h-240:"
            f"box=1:boxcolor=black@0.82:boxborderw=26")
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-i", src,
         "-t", f"{dur:.3f}", "-vf", ",".join(vf), "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", "-an", out])

def card_segment(card, dur, idx, out):
    frames = max(2, round(dur * FPS))
    z = "min(1.0+0.00022*on,1.12)" if idx % 2 == 0 else "max(1.12-0.00022*on,1.0)"
    vf = (f"scale=2400:1350,zoompan=z='{z}':d={frames}"
          f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps={FPS},"
          f"format=yuv420p")
    run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", card,
         "-vf", vf, "-t", f"{dur:.3f}", "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-an", out])

def main():
    script_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        BASE, "content", "current", "script.json")
    with open(script_path) as f:
        script = json.load(f)
    with open(os.path.join(BASE, "work", "timings.json")) as f:
        tm = json.load(f)

    paras = []
    for si, sec in enumerate(script["sections"]):
        for para in sec["paragraphs"]:
            paras.append((si, sec, para))

    rng = random.Random(datetime.date.today().toordinal() * 6151 + len(paras))
    broll = Broll(rng)
    seg_dir = os.path.join(BASE, "work", "segs")
    os.makedirs(seg_dir, exist_ok=True)

    concat, sfx_events = [], []
    n = len(tm["items"])
    for it in tm["items"]:
        i, dur, t0 = it["idx"], it["dur"], it["start"]
        si, sec, para = paras[i]
        card = os.path.join(BASE, "work", "cards", f"c_{i:04d}.jpg")
        seg = os.path.join(seg_dir, f"s_{i:04d}.mp4")
        concat.append(f"file '{seg}'")
        fresh = not (os.path.exists(seg) and os.path.getsize(seg) > 5000)

        is_hook = (si == 0) and broll.any()
        is_interlude = (si > 0) and broll.any() and (i % BODY_BROLL_EVERY == 2)

        if is_hook:
            # Vox-style: split narration span into fast cuts, each a new scene
            cuts = max(1, round(dur / CUT_LEN))
            cut_d = dur / cuts
            parts = []
            for k in range(cuts):
                part = os.path.join(seg_dir, f"h_{i:04d}_{k}.mp4")
                if fresh:
                    src, start = broll.pick(cut_d)
                    broll_cut(src, start, cut_d, part,
                              title=para.get("card_title") if k == 0 else None,
                              flash=True)
                parts.append(f"file '{part}'")
                sfx_events.append(("whoosh", t0 + k * cut_d))
            if fresh:
                lst = os.path.join(seg_dir, f"h_{i:04d}.txt")
                with open(lst, "w") as f:
                    f.write("\n".join(parts) + "\n")
                run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                     "-i", lst, "-c", "copy", seg])
        elif is_interlude:
            if fresh:
                src, start = broll.pick(dur)
                broll_cut(src, start, dur, seg,
                          title=para.get("card_title") or sec["heading"], flash=True)
            sfx_events.append(("whoosh", t0))
        else:
            if fresh:
                card_segment(card, dur, i, seg)
            if it["para"] == 0:  # section start on a card
                sfx_events.append(("impact", t0))
        if i % 10 == 0:
            print(f"[assemble] segment {i+1}/{n}", flush=True)

    listfile = os.path.join(seg_dir, "concat.txt")
    with open(listfile, "w") as f:
        f.write("\n".join(concat) + "\n")
    silent = os.path.join(BASE, "work", "video_noaudio.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", listfile, "-c", "copy", silent])

    # ---- audio: narration + SFX bed ----
    narration = os.path.join(BASE, "work", "narration.wav")
    mixed = os.path.join(BASE, "work", "narration_sfx.wav")
    try:
        from pydub import AudioSegment
        base_a = AudioSegment.from_wav(narration)
        wh = AudioSegment.from_wav(os.path.join(BASE, "work", "sfx", "whoosh.wav")) - 14
        im = AudioSegment.from_wav(os.path.join(BASE, "work", "sfx", "impact.wav")) - 12
        for kind, ts in sfx_events:
            ms = max(0, int(ts * 1000) - 120)  # slight pre-roll
            base_a = base_a.overlay(wh if kind == "whoosh" else im, position=ms)
        base_a.export(mixed, format="wav")
        print(f"[assemble] SFX mixed: {len(sfx_events)} events")
    except Exception as e:
        print(f"[assemble] SFX skipped ({e}) — using plain narration")
        mixed = narration

    final = os.path.join(BASE, "work", "final.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-i", silent, "-i", mixed,
         "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
         "-movflags", "+faststart", "-shortest", final])
    print(f"[assemble] DONE -> work/final.mp4 ({ffdur(final)/60:.1f} min)")

if __name__ == "__main__":
    main()
