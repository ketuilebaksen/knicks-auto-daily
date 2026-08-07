#!/usr/bin/env python3
"""
photos.py — build the photo library for today's video.

Priority 1: photos the owner uploaded to the GitHub release tagged `photos`
            (already downloaded into work/photos by the workflow).
Priority 2: auto-fetch pro photos (>=1080px wide) from Wikimedia Commons for
            player names mentioned in the script. Credits are collected into
            work/photo_credits.txt and appended to the video description.

Usage: python3 scripts/photos.py content/current/script.json
"""
import json, os, re, sys, urllib.parse, urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "work", "photos")
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "knicks-auto-daily/1.0 (github actions; contact: repo owner)"}

NAMES = ["Jalen Brunson", "Karl-Anthony Towns", "OG Anunoby", "Mikal Bridges",
         "Josh Hart", "Miles McBride", "Mitchell Robinson", "Landry Shamet",
         "Tyler Kolek", "Pacome Dadiet", "Guerschon Yabusele", "Jordan Clarkson",
         "Mike Brown", "Madison Square Garden", "New York Knicks"]

def fetch_json(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def search_photo(term):
    try:
        d = fetch_json({
            "action": "query", "format": "json",
            "generator": "search",
            "gsrsearch": f'filetype:bitmap "{term}"',
            "gsrnamespace": "6", "gsrlimit": "5",
            "prop": "imageinfo",
            "iiprop": "url|size|extmetadata", "iiurlwidth": "1920"})
    except Exception as e:
        print(f"[photos] search failed for {term}: {e}")
        return None
    pages = (d.get("query") or {}).get("pages") or {}
    best = None
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        w, h = ii.get("width", 0), ii.get("height", 0)
        if w >= 1080 and h >= 700 and ii.get("thumburl"):
            if not best or w * h > best[1]:
                meta = ii.get("extmetadata") or {}
                artist = re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip()
                lic = (meta.get("LicenseShortName") or {}).get("value", "")
                best = (ii["thumburl"], w * h, artist, lic, p.get("title", ""))
    return best

def main():
    os.makedirs(OUT, exist_ok=True)
    existing = [f for f in os.listdir(OUT)
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    if len(existing) >= 5:
        print(f"[photos] owner library present ({len(existing)} photos) — skipping auto-fetch")
        return
    with open(sys.argv[1]) as f:
        script = json.load(f)
    text = json.dumps(script)
    wanted = [n for n in NAMES if n.split()[-1].lower() in text.lower()][:8]
    if "New York Knicks" not in wanted:
        wanted.append("New York Knicks")
    credits, n_ok = [], 0
    for term in wanted:
        best = search_photo(term + " basketball" if "Garden" not in term else term)
        if not best:
            continue
        url, _, artist, lic, title = best
        fname = re.sub(r"[^a-z0-9]+", "_", term.lower()) + ".jpg"
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r, \
                 open(os.path.join(OUT, fname), "wb") as o:
                o.write(r.read())
            n_ok += 1
            if artist or lic:
                credits.append(f"{term}: {title.replace('File:','')} — {artist} ({lic}), via Wikimedia Commons")
            print(f"[photos] {term} ok")
        except Exception as e:
            print(f"[photos] download failed {term}: {e}")
    if credits:
        with open(os.path.join(BASE, "work", "photo_credits.txt"), "w") as f:
            f.write("\n".join(credits) + "\n")
    print(f"[photos] DONE — {n_ok} auto photos")

if __name__ == "__main__":
    main()
