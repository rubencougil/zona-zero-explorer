#!/usr/bin/env python3
"""
import_rockzone.py
─────────────────
Scrapes Rubén Cougil's articles from rockzonemag.com and saves them
as Markdown files in the data/ directory.

Usage:
    python3 import_rockzone.py          # dry-run (shows what would be imported)
    python3 import_rockzone.py --save   # actually save new files
    python3 import_rockzone.py --save --force   # overwrite existing files too

After importing, run  python3 build.py  to regenerate public/data.json.
"""

import re
import os
import sys
import time
import html as htmllib
import urllib.request
import urllib.parse
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
SEARCH_URL   = "https://www.rockzonemag.com/?s=ruben+cougil"
DATA_DIR     = os.path.join(os.path.dirname(__file__), "data")
AUTHOR_SIG   = re.compile(r"RUB[EÉ]N COUGIL", re.I)
REQUEST_DELAY = 1.0          # seconds between requests (be polite)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}

# ── HTTP helpers ──────────────────────────────────────────────────────────────
def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="replace")


def h(text):
    """Unescape HTML entities and strip tags."""
    return htmllib.unescape(re.sub(r"<[^>]+>", "", text)).strip()


# ── Search-result scraping ────────────────────────────────────────────────────
def get_article_urls():
    """Return all article URLs from all search result pages."""
    urls = []
    page = 1
    while True:
        if page == 1:
            url = SEARCH_URL
        else:
            url = f"https://www.rockzonemag.com/page/{page}/?s=ruben+cougil"

        print(f"  Fetching search page {page}: {url}")
        try:
            html_src = fetch(url)
        except Exception as e:
            print(f"  ⚠ Search page {page} error: {e}")
            break

        found = re.findall(
            r'<h3[^>]*>\s*<a href="(https://www\.rockzonemag\.com/[^"]+)"',
            html_src,
        )
        if not found:
            break

        urls.extend(found)

        # Check for a next page link
        if not re.search(r'href="[^"]+/page/\d+[^"]*"', html_src):
            break
        page += 1
        time.sleep(REQUEST_DELAY)

    return list(dict.fromkeys(urls))  # deduplicate preserving order


# ── Article scraping ──────────────────────────────────────────────────────────
def parse_article(url):
    """
    Fetch and parse one article page.
    Returns a dict or None if not authored by Rubén Cougil.
    """
    html_src = fetch(url)

    # ── Title ──────────────────────────────────────────────────────────────
    title_m = re.search(r"<h1[^>]*>(.*?)</h1>", html_src, re.S)
    title = h(title_m.group(1)) if title_m else ""
    if not title:
        return None

    # ── Date ───────────────────────────────────────────────────────────────
    date_m = re.search(r'<time[^>]*datetime="([^"]+)"', html_src)
    pub_date = ""
    if date_m:
        try:
            dt = datetime.fromisoformat(date_m.group(1).replace("Z", "+00:00"))
            pub_date = dt.strftime("%Y-%m-%d")
        except ValueError:
            pub_date = date_m.group(1)[:10]

    # ── Cover image ────────────────────────────────────────────────────────
    cover_m = re.search(
        r'td-post-featured-image.*?<a href="([^"]+)"', html_src, re.S
    )
    cover_url = cover_m.group(1) if cover_m else ""

    # ── Category / type ────────────────────────────────────────────────────
    # Guess from URL slug
    slug_raw = url.rstrip("/").split("/")[-1]
    if any(x in slug_raw for x in ["entrevista", "interview"]):
        content_type = "entrevista"
    elif any(x in slug_raw for x in ["cronica", "directo", "live", "concierto"]):
        content_type = "crónica"
    else:
        content_type = "reseña"

    # ── Body content ───────────────────────────────────────────────────────
    start = html_src.find("<!-- content -->")
    end   = html_src.find("<!-- /content -->", start)
    if start < 0:
        return None

    block = html_src[start: end if end > start else start + 15000]

    # Remove noise blocks before converting
    block = re.sub(r"<script[^>]*>.*?</script>", "", block, flags=re.S)
    block = re.sub(r"<style[^>]*>.*?</style>",   "", block, flags=re.S)
    block = re.sub(r"<iframe[^>]*>.*?</iframe>",  "", block, flags=re.S)
    # Remove social share, tags, rating widget, related posts (everything after the last </p>)
    for cls in ["sharedaddy", "td-post-sharing", "td-tags", "td-rating",
                "td-block-related", "td-post-next-prev", "author-box"]:
        block = re.sub(rf'<[^>]+class="[^"]*{cls}[^"]*".*', "", block, flags=re.S)
    block = re.sub(r'<div[^>]*class="[^"]*td-post-featured-image[^"]*".*?</div>', "", block, flags=re.S)

    # Check authorship
    if not AUTHOR_SIG.search(block):
        return None  # not by Rubén Cougil

    # Convert to Markdown
    body_md = html_to_markdown(block)

    # ── Build slug for filename ────────────────────────────────────────────
    clean_title = re.sub(r"[^\w\s-]", "", title.lower())
    clean_title = re.sub(r"[\s_]+", "_", clean_title.strip())
    slug = f"rz_{clean_title[:60]}"

    return {
        "slug":     slug,
        "title":    title,
        "subtitle": pub_date,          # date as subtitle for import context
        "type":     content_type,
        "cover":    cover_url,
        "body":     body_md,
        "url":      url,
    }


# ── HTML → Markdown ───────────────────────────────────────────────────────────
def html_to_markdown(html_src):
    """Very lightweight HTML-to-Markdown converter for article bodies."""

    # Block elements → Markdown equivalents
    html_src = re.sub(r"<h2[^>]*>(.*?)</h2>", lambda m: f"\n## {h(m.group(1))}\n", html_src, flags=re.S)
    html_src = re.sub(r"<h3[^>]*>(.*?)</h3>", lambda m: f"\n### {h(m.group(1))}\n", html_src, flags=re.S)
    html_src = re.sub(r"<h4[^>]*>(.*?)</h4>", lambda m: f"\n#### {h(m.group(1))}\n", html_src, flags=re.S)
    html_src = re.sub(r"<blockquote[^>]*>(.*?)</blockquote>", lambda m: f"\n> {h(m.group(1))}\n", html_src, flags=re.S)

    # Inline elements
    html_src = re.sub(r"<strong[^>]*>(.*?)</strong>", r"**\1**", html_src, flags=re.S)
    html_src = re.sub(r"<b[^>]*>(.*?)</b>",           r"**\1**", html_src, flags=re.S)
    html_src = re.sub(r"<em[^>]*>(.*?)</em>",          r"_\1_",   html_src, flags=re.S)
    html_src = re.sub(r"<i[^>]*>(.*?)</i>",            r"_\1_",   html_src, flags=re.S)
    html_src = re.sub(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"[\2](\1)", html_src, flags=re.S)

    # Paragraphs
    html_src = re.sub(r"<p[^>]*>(.*?)</p>", lambda m: f"\n{m.group(1).strip()}\n", html_src, flags=re.S)

    # Strip remaining tags
    html_src = re.sub(r"<[^>]+>", "", html_src)

    # Unescape entities
    html_src = htmllib.unescape(html_src)

    # Clean up whitespace
    lines = [line.rstrip() for line in html_src.splitlines()]
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))

    # Cut at author signature and discard everything after (widgets, tags, JS…)
    result = re.sub(r"\n+\*{0,2}RUB[EÉ]N COUGIL.*", "", result, flags=re.I | re.S).strip()

    # Remove leftover empty/ad markdown links like [](url), [_](url), [__](url)
    result = re.sub(r"\[_*\]\([^)]+\)\s*", "", result)

    return result.strip()


# ── Markdown file writer ──────────────────────────────────────────────────────
def build_markdown(article):
    """Format article dict as a Markdown file string."""
    lines = [
        article["title"],
        article["subtitle"],
        "",
    ]
    if article["cover"]:
        lines += [f"<!-- cover: {article['cover']} -->", ""]
    if article["url"]:
        lines += [f"<!-- source: {article['url']} -->", ""]
    lines.append(article["body"])
    return "\n".join(lines).strip() + "\n"


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    dry_run = "--save" not in sys.argv
    force   = "--force" in sys.argv

    if dry_run:
        print("DRY RUN — pass --save to actually write files\n")

    print("Step 1: Collecting article URLs from search results…")
    urls = get_article_urls()
    print(f"  Found {len(urls)} article URLs\n")

    imported = 0
    skipped_author = 0
    skipped_exists = 0
    errors = 0

    print("Step 2: Fetching and parsing articles…")
    for url in urls:
        time.sleep(REQUEST_DELAY)
        try:
            article = parse_article(url)
        except Exception as e:
            print(f"  ✗ ERROR  {url}\n    {e}")
            errors += 1
            continue

        if article is None:
            print(f"  – SKIP   (not by Rubén Cougil) {url}")
            skipped_author += 1
            continue

        dest = os.path.join(DATA_DIR, article["slug"] + ".md")
        exists = os.path.exists(dest)

        if exists and not force:
            print(f"  = EXISTS {article['title'][:55]}")
            skipped_exists += 1
            continue

        action = "SAVE " if not exists else "UPDATE"
        print(f"  ✓ {action} {article['title'][:55]}")
        print(f"         → {article['slug']}.md  [{article['type']}]  {article['subtitle']}")

        if not dry_run:
            with open(dest, "w", encoding="utf-8") as f:
                f.write(build_markdown(article))
            imported += 1

    print(f"""
─────────────────────────────────────────
  Articles checked : {len(urls)}
  Authored by you  : {len(urls) - skipped_author}
  Already existed  : {skipped_exists}
  {"Would import" if dry_run else "Imported"}  : {len(urls) - skipped_author - skipped_exists} {'(dry run)' if dry_run else ''}
  Errors           : {errors}
─────────────────────────────────────────""")

    if dry_run and (len(urls) - skipped_author - skipped_exists) > 0:
        print("Run with --save to write the files, then: python3 build.py")
    elif not dry_run and imported > 0:
        print("Done! Run  python3 build.py  to regenerate public/data.json")


if __name__ == "__main__":
    main()
