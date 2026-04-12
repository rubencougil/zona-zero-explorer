#!/usr/bin/env python3
"""
Build script: parses all .md files in data/ and generates public/data.json
Fetches album cover art from iTunes Search API (cached in cover_cache.json).
"""
import os
import re
import json
import time
import urllib.request
import urllib.parse

COVER_CACHE_FILE = "cover_cache.json"

DATA_DIR = "data"
OUTPUT = "public/data.json"


def clean_text(text):
    """Remove backslash escapes from Pandoc-converted markdown."""
    return text.replace('\\"', '"').replace("\\'", "'")


def detect_type(subtitle, body):
    """Classify content as reseña, crónica, or entrevista."""
    # Interviews have Q&A format with #### ¿ headings
    if "#### ¿" in body or re.search(r'####\s+¿', body):
        return "entrevista"
    # Also detect interviews by intro mentioning entrevista + parenthesized date
    if re.match(r'^\(\d{1,2}-\d{1,2}-\d{4}\)$', subtitle.strip()):
        if re.search(r'entrevista|pregunta|respuesta|zona.zero', body.lower()):
            return "entrevista"
    # Album reviews: subtitle matches "Album Title", Year
    if re.search(r'"[^"]{2,}", \d{4}', subtitle) or re.search(r'"[^"]{2,}",\s*\d{4}', subtitle):
        return "reseña"
    # Concert chronicles: subtitle has date + venue (no quotes around it)
    if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', subtitle) or \
       re.search(r'\d{1,2}\s+de\s+\w+\s+de\s+\d{4}', subtitle, re.I) or \
       re.search(r'\d{1,2}\s+\w+\s+de\s+\d{4}', subtitle, re.I):
        return "crónica"
    # Default: album review
    return "reseña"


def load_cover_cache():
    if os.path.exists(COVER_CACHE_FILE):
        with open(COVER_CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cover_cache(cache):
    with open(COVER_CACHE_FILE, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def fetch_cover_art(artist, album, cache):
    key = f"{artist}|||{album}".lower()
    if key in cache:
        return cache[key]

    query = f"{artist} {album}"
    encoded = urllib.parse.quote_plus(query)
    url = f"https://itunes.apple.com/search?term={encoded}&media=music&entity=album&limit=5&country=es"
    cover = ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("resultCount", 0) > 0:
            art = data["results"][0].get("artworkUrl100", "")
            if art:
                cover = art.replace("100x100bb", "500x500bb")
    except Exception as e:
        print(f"  ⚠ Cover art: {artist} / {album} → {e}")

    # Only cache successes so failures get retried next run
    if cover:
        cache[key] = cover
    time.sleep(0.4)
    return cover


def extract_album_name(subtitle):
    m = re.match(r'"([^"]+)"', subtitle)
    return m.group(1) if m else ""


def fetch_artist_photo(artist, cache):
    """Fallback: fetch artist photo from Deezer API."""
    key = f"deezer|||{artist}".lower()
    if key in cache:
        return cache[key]

    encoded = urllib.parse.quote_plus(artist)
    url = f"https://api.deezer.com/search/artist?q={encoded}&limit=1"
    photo = ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        results = data.get("data", [])
        if results:
            # picture_big is 500x500, picture_xl is 1000x1000
            photo = results[0].get("picture_big", "") or results[0].get("picture_medium", "")
            # Skip generic Deezer placeholder: has empty hash (double slash) in path
            if "images/artist//" in photo:
                photo = ""
    except Exception as e:
        print(f"  ⚠ Artist photo: {artist} → {e}")

    if photo:
        cache[key] = photo
    time.sleep(0.25)
    return photo


    m = re.match(r'"([^"]+)"', subtitle)
    return m.group(1) if m else ""


def parse_file(path):
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    # Extract embedded cover URL (set by import_rockzone.py)
    embedded_cover = ""
    cover_match = re.search(r'<!--\s*cover:\s*(https?://\S+)\s*-->', raw)
    if cover_match:
        embedded_cover = cover_match.group(1)

    # Strip HTML comments before processing
    raw_clean = re.sub(r'<!--.*?-->', '', raw, flags=re.S)

    content = clean_text(raw_clean)
    lines = content.split("\n")

    title = ""
    subtitle = ""
    body_start = 0

    # Extract title from first non-empty line
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            title = stripped[2:].strip()
        else:
            title = stripped
        body_start = i + 1
        break

    # Extract subtitle (first non-empty line after title)
    for i in range(body_start, len(lines)):
        stripped = lines[i].strip()
        if stripped:
            subtitle = stripped
            body_start = i + 1
            break

    body = "\n".join(lines[body_start:]).strip()
    content_type = detect_type(subtitle, body)

    # Clean excerpt: strip markdown syntax for preview text
    excerpt_clean = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', body)
    excerpt_clean = re.sub(r'#+\s+', '', excerpt_clean)
    excerpt_clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', excerpt_clean)
    excerpt_clean = re.sub(r'\s+', ' ', excerpt_clean).strip()
    excerpt = excerpt_clean[:280]
    if len(excerpt_clean) > 280:
        # Cut at last word boundary
        excerpt = excerpt[:excerpt.rfind(' ')] + '…'

    slug = os.path.basename(path).replace(".md", "")

    return {
        "slug": slug,
        "title": title,
        "subtitle": subtitle,
        "type": content_type,
        "body": body,
        "excerpt": excerpt,
        "cover_url": embedded_cover,  # pre-filled if from import_rockzone; overridden in main() otherwise
    }


def main():
    articles = []
    errors = []

    for fname in sorted(os.listdir(DATA_DIR)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(DATA_DIR, fname)
        try:
            article = parse_file(path)
            articles.append(article)
        except Exception as e:
            errors.append(f"  ERROR {fname}: {e}")

    # Sort alphabetically by title
    articles.sort(key=lambda x: x["title"].lower())

    # Fetch cover art for reviews; fallback to artist photo via Deezer
    cover_cache = load_cover_cache()

    # Only fetch iTunes for reviews that don't already have an embedded cover
    reviews = [a for a in articles if a["type"] == "reseña" and not a.get("cover_url")]
    needs_itunes = [a for a in reviews if not cover_cache.get(f"{a['title']}|||{extract_album_name(a['subtitle'])}".lower())]
    if needs_itunes:
        print(f"Fetching iTunes covers for {len(needs_itunes)} articles (cached: {len(reviews) - len(needs_itunes)})…")
    for a in reviews:
        album = extract_album_name(a["subtitle"])
        if album:
            a["cover_url"] = fetch_cover_art(a["title"], album, cover_cache)

    # Fallback: for any article still without a cover, try Deezer artist photo
    without_cover = [a for a in articles if not a.get("cover_url")]
    needs_deezer = [a for a in without_cover if not cover_cache.get(f"deezer|||{a['title']}".lower())]
    if needs_deezer:
        print(f"Fetching Deezer artist photos for {len(needs_deezer)} articles (cached: {len(without_cover) - len(needs_deezer)})…")
    for a in without_cover:
        photo = fetch_artist_photo(a["title"], cover_cache)
        if photo:
            a["cover_url"] = photo

    save_cover_cache(cover_cache)

    # Sort alphabetically by title
    articles.sort(key=lambda x: x["title"].lower())

    os.makedirs("public", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    # Stats
    types = {}
    for a in articles:
        types[a["type"]] = types.get(a["type"], 0) + 1

    print(f"✓ Generated {len(articles)} articles → {OUTPUT}")
    for t, count in sorted(types.items()):
        print(f"  {t}: {count}")
    if errors:
        print("Errors:")
        for e in errors:
            print(e)


if __name__ == "__main__":
    main()
