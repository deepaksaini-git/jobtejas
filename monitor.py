#!/usr/bin/env python3
"""
Govt Job Alert Monitor
----------------------
Sarkari websites ke notice/news pages check karta hai aur naya link milte hi
Telegram par alert bhejta hai (category, title, date, summary, links).

Use:
    python monitor.py          -> normal run (Telegram alerts bhejta hai)
    python monitor.py --test   -> sirf check karta hai ki har site se kitne links mil rahe hain
"""
import hashlib
import html
import io
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import ssl

import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup

try:
    import lxml  # noqa: F401
    PARSER = "lxml"
except ImportError:      # Termux par lxml na ho to built-in parser
    PARSER = "html.parser"

requests.packages.urllib3.disable_warnings()

BASE = os.path.dirname(os.path.abspath(__file__))
SOURCES_FILE = os.getenv("SOURCES_FILE", os.path.join(BASE, "sources.json"))
SEEN_FILE = os.getenv("SEEN_FILE", os.path.join(BASE, "seen.json"))

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_IDS = [c.strip() for c in os.getenv("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]

TIMEOUT = (8, 15)   # (connect, read) seconds
MAX_NEW_PER_SOURCE = 15      # isse zyada naye links = shayad site ka layout badla, spam nahi bhejenge
MAX_SEEN_PER_SOURCE = 3000
IST = timezone(timedelta(hours=5, minutes=30))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
}

# Order important hai: pehle match hone wali category use hoti hai
CATEGORIES = [
    ("🎫 Admit Card", ["admit card", "admit-card", "admitcard", "hall ticket", "call letter",
                       "e-admit", "city intimation", "प्रवेश पत्र", "एडमिट कार्ड"]),
    ("🔑 Answer Key", ["answer key", "answerkey", "response sheet", "objection", "उत्तर कुंजी"]),
    ("📊 Result", ["result", "merit list", "cut off", "cut-off", "final selection", "scorecard",
                   "score card", "selected candidates", "परिणाम", "रिजल्ट"]),
    ("📚 Syllabus", ["syllabus", "exam pattern", "पाठ्यक्रम", "सिलेबस"]),
    ("📅 Exam Date / Schedule", ["exam date", "exam schedule", "examination schedule", "time table",
                                 "timetable", "tentative schedule", "calendar", "reschedul",
                                 "postponed", "परीक्षा तिथि", "कार्यक्रम"]),
    ("💼 Latest Job / Notification", ["recruitment", "vacancy", "vacancies", "notification",
                                      "advertisement", "advt", "apply online", "online application",
                                      "walk-in", "walk in", "bharti", "career", "engagement",
                                      "भर्ती", "विज्ञप्ति", "अधिसूचना", "रिक्त"]),
]
KEYWORDS = [k for _, ks in CATEGORIES for k in ks]

GENERIC_TEXT = {"click here", "download", "view", "view more", "read more", "more", "link",
                "pdf", "here", "apply", "details", "english", "hindi", "क्लिक करें"}

DATE_PATTERNS = [
    r"\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b",
    r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*[\s,.\-]+\d{2,4}\b",
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b",
]


# ----------------------------------------------------------------- helpers
def now_ist():
    return datetime.now(IST)


class LegacySSLAdapter(HTTPAdapter):
    """Purani sarkari sites (weak ciphers / legacy renegotiation) ke liye."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
        except ssl.SSLError:
            pass
        ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
        kwargs["ssl_context"] = ctx
        super().init_poolmanager(*args, **kwargs)


def fetch(url, stream=False):
    """Normal -> verify=False -> legacy SSL, is order mein try karta hai."""
    kw = dict(headers=HEADERS, timeout=TIMEOUT, stream=stream)
    try:
        return requests.get(url, **kw)
    except requests.exceptions.SSLError:
        pass
    try:
        return requests.get(url, verify=False, **kw)
    except requests.exceptions.SSLError:
        pass
    sess = requests.Session()
    sess.mount("https://", LegacySSLAdapter())
    return sess.get(url, verify=False, **kw)


def norm_url(u):
    p = urlparse(u)
    return f"{p.scheme}://{p.netloc.lower()}{p.path.rstrip('/')}" + (f"?{p.query}" if p.query else "")


def item_id(u):
    return hashlib.sha1(norm_url(u).encode()).hexdigest()[:16]


def detect_category(text):
    t = text.lower()
    for name, kws in CATEGORIES:
        if any(k in t for k in kws):
            return name
    return None


def find_date(text):
    for pat in DATE_PATTERNS:
        m = re.search(pat, text, flags=re.I)
        if m:
            return m.group(0)
    return None


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


# ----------------------------------------------------------------- scraping
def scrape_source(src):
    """Return (items, error). item = dict(title, url, date, category)."""
    try:
        r = fetch(src["url"])
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        return [], f"{type(e).__name__}: {e}"

    soup = BeautifulSoup(r.content, PARSER)
    items, seen_urls = [], set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        url = urljoin(src["url"], href)
        if not url.startswith("http"):
            continue

        title = clean(a.get_text(" ")) or clean(a.get("title", ""))
        parent_text = clean(a.parent.get_text(" ")) if a.parent else ""
        if title.lower() in GENERIC_TEXT or len(title) < 6:
            title = parent_text[:160] or title
        if len(title) < 6:
            continue

        haystack = f"{title} {os.path.basename(urlparse(url).path)}"
        category = detect_category(haystack)
        if not category:
            continue

        key = norm_url(url)
        if key in seen_urls:
            continue
        seen_urls.add(key)

        items.append({
            "title": title[:220],
            "url": url,
            "date": find_date(title) or find_date(parent_text[:300]),
            "category": category,
        })
    return items, None


def summarize(url):
    """Link ke andar se chhota summary nikalta hai (PDF ka pehla page ya HTML meta description)."""
    try:
        r = fetch(url, stream=True)
        ctype = r.headers.get("Content-Type", "").lower()
        if "pdf" in ctype or url.lower().split("?")[0].endswith(".pdf"):
            data = r.raw.read(2_500_000, decode_content=True)
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text = clean(reader.pages[0].extract_text() or "")
        elif "html" in ctype:
            soup = BeautifulSoup(r.raw.read(600_000, decode_content=True), PARSER)
            meta = soup.find("meta", attrs={"name": "description"}) or \
                soup.find("meta", attrs={"property": "og:description"})
            text = clean(meta.get("content", "")) if meta else ""
            if not text:
                text = clean(" ".join(p.get_text(" ") for p in soup.find_all("p")[:4]))
        else:
            return ""
        return text[:280] + ("…" if len(text) > 280 else "")
    except Exception:  # noqa: BLE001
        return ""


# ----------------------------------------------------------------- telegram
def tg_send(text):
    if not TOKEN or not CHAT_IDS:
        print("[!] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID set nahi hai")
        return False
    ok = True
    for chat in CHAT_IDS:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                json={"chat_id": chat, "text": text[:4000], "parse_mode": "HTML",
                      "disable_web_page_preview": True},
                timeout=20,
            )
            if r.status_code == 429:
                time.sleep(r.json().get("parameters", {}).get("retry_after", 5))
                r = requests.post(
                    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                    json={"chat_id": chat, "text": text[:4000], "parse_mode": "HTML",
                          "disable_web_page_preview": True},
                    timeout=20,
                )
            if not r.ok:
                print("[!] Telegram error:", r.text)
                ok = False
        except Exception as e:  # noqa: BLE001
            print("[!] Telegram exception:", e)
            ok = False
    return ok


def build_message(item, src, summary):
    e = html.escape
    date_line = item["date"] or f"Detected: {now_ist().strftime('%d %b %Y, %I:%M %p')} IST"
    lines = [
        f"<b>{item['category']}</b>",
        f"<b>{e(item['title'])}</b>",
        "",
        f"🏛 {e(src['name'])}",
        f"📅 {e(date_line)}",
    ]
    if summary:
        lines.append(f"📝 {e(summary)}")
    lines += [
        "",
        f"🔗 <a href=\"{e(item['url'], quote=True)}\">Notification / Document</a>",
        f"🌐 <a href=\"{e(src['url'], quote=True)}\">Official Website</a>",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------- main
def main():
    test_mode = "--test" in sys.argv
    sources = json.load(open(SOURCES_FILE, encoding="utf-8"))
    seen = json.load(open(SEEN_FILE, encoding="utf-8")) if os.path.exists(SEEN_FILE) else {}

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(scrape_source, sources))

    if test_mode:
        for src, (items, err) in zip(sources, results):
            status = f"ERROR {err}" if err else f"{len(items)} relevant links"
            print(f"{src['name']:<28} {status}")
        return

    changed, sent = False, 0
    failed = []
    for src, (items, err) in zip(sources, results):
        name = src["name"]
        if err:
            print(f"[x] {name}: {err[:120]}")
            failed.append(name)
            continue
        if not items:
            print(f"[-] {name}: koi relevant link nahi mila")
            continue

        ids = [item_id(i["url"]) for i in items]

        # Nayi site pehli baar: chupchaap seed karo, alert mat bhejo
        if name not in seen:
            seen[name] = ids
            changed = True
            print(f"[seed] {name}: {len(ids)} links save kiye")
            continue

        known = set(seen[name])
        fresh = [i for i, h in zip(items, ids) if h not in known]
        if not fresh:
            continue

        seen[name] = (seen[name] + [item_id(i["url"]) for i in fresh])[-MAX_SEEN_PER_SOURCE:]
        changed = True

        if len(fresh) > MAX_NEW_PER_SOURCE:
            tg_send(f"⚠️ <b>{html.escape(name)}</b>: ek saath {len(fresh)} naye links mile "
                    f"(shayad website ka layout badla hai). Check karein: {html.escape(src['url'])}")
            continue

        for item in fresh:
            msg = build_message(item, src, summarize(item["url"]))
            if tg_send(msg):
                sent += 1
            time.sleep(0.6)

    if changed:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(seen, f, ensure_ascii=False, indent=0)
    if failed:
        print(f"\nFAILED SITES ({len(failed)}): " + ", ".join(failed))
    print(f"Done. {sent} alert(s) bheje gaye.")


if __name__ == "__main__":
    main()
