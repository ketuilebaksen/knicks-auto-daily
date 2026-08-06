#!/usr/bin/env python3
"""
assemble.py — build final video: per-paragraph card segments (slow Ken Burns zoom)
concatenated and muxed with narration.

Usage: python3 scripts/assemble.py            -> work/final.mp4
"""
import json, os, subprocess, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 24

def main():
    with open(os.path.join(BASE, "work", "timings.json")) as f:
        tm = json.load(f)
    seg_dir = os.path.join(BASE, "work", "segs")
    os.makedirs(seg_dir, exist_ok=True)
    concat = []
    n = len(tm["items"])
    for it in tm["items"]:
        i, dur = it["idx"], it["dur"]
        card = os.path.join(BASE, "work", "cards", f"c_{i:04d}.jpg")
        seg = os.path.join(seg_dir, f"s_{i:04d}.mp4")
        concat.append(f"file '{seg}'")
        if os.path.exists(seg) and os.path.getsize(seg) > 5000:
            continue
        frames = max(2, round(dur * FPS))
        # slow zoom in (even idx) / out (odd idx)
        if i % 2 == 0:
            z = f"min(1.0+0.00022*on,1.12)"
        else:
            z = f"max(1.12-0.00022*on,1.0)"
        vf = (f"scale=2400:1350,zoompan=z='{z}':d={frames}"
              f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps={FPS},"
              f"format=yuv420p")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", card,
                        "-vf", vf, "-t", f"{dur:.3f}", "-r", str(FPS),
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-an", seg], check=True)
        print(f"[assemble] segment {i+1}/{n}", flush=True)

    listfile = os.path.join(seg_dir, "concat.txt")
    with open(listfile, "w") as f:
        f.write("\n".join(concat) + "\n")
    final = os.path.join(BASE, "work", "final.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "concat", "-safe", "0", "-i", listfile,
                    "-i", os.path.join(BASE, "work", "narration.wav"),
                    "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "160k",
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-movflags", "+faststart", "-shortest", final], check=True)
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", final], capture_output=True, text=True)
    print(f"[assemble] DONE -> work/final.mp4 ({float(r.stdout)/60:.1f} min)")

if __name__ == "__main__":
    main()
