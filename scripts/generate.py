#!/usr/bin/env python3
"""
generate.py — daily script + metadata writer. Runs in GitHub Actions.
Calls Claude (Anthropic API) with server-side web search to research today's
NY Knicks news and produce content/current/script.json + meta.json.

Env: ANTHROPIC_API_KEY  (required)
     MODEL              (default: claude-sonnet-4-5)
     TARGET_MINUTES     (default: 30)
"""
import json, os, re, sys, datetime

try:
    import anthropic
except ImportError:
    sys.exit("pip install anthropic")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUR = os.path.join(BASE, "content", "current")
LOG = os.path.join(BASE, "content", "topics_log.txt")
MODEL = os.environ.get("MODEL", "claude-sonnet-4-5")
MINUTES = int(os.environ.get("TARGET_MINUTES", "30"))
WORDS = MINUTES * 150  # ~150 wpm narration

SCHEMA_HINT = """
Return ONE JSON object inside a ```json fenced block, exactly this shape:
{
 "title": "<=95 char clickable title",
 "thumbnail_lines": ["MAX 3 LINES", "SHORT PUNCHY", "ALL CAPS"],
 "sections": [
   {"heading": "SHORT SECTION TITLE",
    "paragraphs": [
      {"text": "60-110 word narration paragraph...",
       "card_title": "<=8 word on-screen title",
       "card_lines": ["2-4 short on-screen bullets", "stats/key facts"]}
    ]}
 ],
 "meta": {
   "description": "2-3 paragraph YouTube description + hashtags (#Knicks #NBA #NewYorkKnicks) + line: 'Narration is AI-generated. All commentary and analysis is original.'",
   "tags": ["15-20 seo tags"]
 }
}
"""

def build_prompt(today, recent_topics):
    return f"""Today is {today}. You write the daily episode for "NY Knicks Daily",
a faceless YouTube channel. Use web search NOW to research today's New York Knicks
news: trades, rumors, injuries, quotes, games (if in season, yesterday's game is the
lead story), Summer League, roster analysis. Check multiple sources (ESPN, SNY,
New York Post, HoopsHype, RealGM). If news is thin, add one deep-dive topic
(roster analysis, historical Knicks story, player profile, season projection).

AVOID repeating these recent topics:
{recent_topics or "(none)"}

Then write an energetic, conversational ~{WORDS}-word English narration script
(target {MINUTES} minutes at ~150 wpm). Short sentences. No abbreviations that read
badly aloud (say "points per game", not "PPG"). 6-9 sections, 45-60 paragraphs total,
60-110 words each. EVERY paragraph must have card_title and card_lines filled.
Total word count across all paragraph texts MUST be between {WORDS-500} and {WORDS+300}.

{SCHEMA_HINT}
Output ONLY the fenced JSON block, no other prose after your research."""

def extract_json(text):
    m = re.findall(r"```json\s*(.*?)```", text, re.S)
    raw = m[-1] if m else text[text.find("{"):text.rfind("}") + 1]
    return json.loads(raw)

def validate(d):
    words = sum(len(p["text"].split()) for s in d["sections"] for p in s["paragraphs"])
    n_para = sum(len(s["paragraphs"]) for s in d["sections"])
    assert d.get("title") and d.get("sections") and d.get("meta"), "missing keys"
    for s in d["sections"]:
        for p in s["paragraphs"]:
            assert p.get("text") and p.get("card_title") and p.get("card_lines"), \
                "paragraph missing card fields"
    assert words > WORDS - 1200, f"script too short: {words} words"
    return words, n_para

def main():
    today = datetime.date.today().isoformat()
    recent = ""
    if os.path.exists(LOG):
        recent = "\n".join(open(LOG).read().strip().splitlines()[-14:])

    client = anthropic.Anthropic()
    prompt = build_prompt(today, recent)
    for attempt in range(3):
        with client.messages.stream(
            model=MODEL, max_tokens=32000,
            tools=[{"type": "web_search_20250305", "name": "web_search",
                    "max_uses": 12}],
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            text = "".join(t for t in stream.text_stream)
        try:
            d = extract_json(text)
            words, n_para = validate(d)
            break
        except Exception as e:
            print(f"[generate] attempt {attempt+1} invalid: {e}", flush=True)
            if attempt == 2:
                raise
            prompt = prompt + f"\n\nPrevious attempt failed validation: {e}. Fix it."
    meta = d.pop("meta")
    os.makedirs(CUR, exist_ok=True)
    with open(os.path.join(CUR, "script.json"), "w") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)
    with open(os.path.join(CUR, "meta.json"), "w") as f:
        json.dump({"title": d["title"], "description": meta["description"],
                   "tags": meta["tags"], "privacy": os.environ.get("PRIVACY", "public")},
                  f, indent=1, ensure_ascii=False)
    with open(LOG, "a") as f:
        f.write(f"{today}: {d['title']}\n")
    print(f"[generate] OK — {words} words, {n_para} paragraphs: {d['title']}")

if __name__ == "__main__":
    main()
