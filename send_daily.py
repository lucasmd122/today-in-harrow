#!/usr/bin/env python3
"""Create (and optionally schedule) tomorrow's Harrow Online Daily issue via the beehiiv Create Post API.

Default is --dry-run: prints the payload, makes NO call to beehiiv. Standard library only.
Secrets come from the environment only (BEEHIIV_API_KEY) and are never printed.
"""
import argparse, datetime as dt, email.utils, json, os, sys, urllib.error, urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
UTC = dt.timezone.utc
PUB_ID = os.environ.get("BEEHIIV_PUBLICATION_ID", "pub_ff7fdfb2-9799-457a-b586-cf01bcbda503")
API = "https://api.beehiiv.com/v2"
SUBJECT = "Harrow Online Daily"
PREVIEW = "News, what's on and today's weather and travel in Harrow"
NEWS_FEED = "https://harrowonline.org/category/news/feed/"
EVENTS_FEED = "https://harrowonline.org/category/events/feed/"
TODAY_FEED = "https://lucasmd122.github.io/today-in-harrow/feed.xml"
CONTACT = "https://harrowonline.org/contact-us/"
RED, TEXT, WHITE = "#D82028", "#1A1A1A", "#FFFFFF"
SEND_HOUR = 9
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
MAX_AGE_DAYS = {"news": 7, "events": 45}


def log(msg):
    print(msg, flush=True)


def fail(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


# ---------- dates ----------
def next_weekday(today):
    d = today + dt.timedelta(days=1)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def send_time_utc(issue_date):
    local = dt.datetime.combine(issue_date, dt.time(SEND_HOUR, 0), tzinfo=LONDON)
    return local, local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def post_title(issue_date):
    # Unique per day, used to detect duplicates. No em dashes.
    return f"{SUBJECT}, {issue_date.strftime('%A')} {issue_date.day} {issue_date.strftime('%B %Y')}"


# ---------- payload ----------
def vs(**extra):
    base = {"background_color": WHITE, "text_color": TEXT}
    base.update(extra)
    return base


def rss(url, count, *, thumb, desc, content=False, cta=False, layout="1-col"):
    return {
        "type": "rss",
        "rssFeedUrl": url,
        "selectionMode": "count",
        "articlesToShow": count,
        "articleLayout": layout,
        "refreshOnSend": True,
        "showArticleTitle": True,
        "showArticleThumbnail": thumb,
        "thumbnailPosition": "Above Title",
        "showDescription": desc,
        "showContent": content,
        "showAuthor": False,
        "showCategories": False,
        "showPublishedDate": False,
        "showCta": cta,
        "ctaStyle": "Title and thumbnail as link" if thumb else "Title as link",
        "visual_settings": vs(),
    }


def build_payload(issue_date, status, segment_id, full_list):
    local, sched = send_time_utc(issue_date)
    blocks = [
        {"type": "paragraph", "plaintext": "Good morning, here's what's happening in Harrow today.",
         "textAlignment": "left", "visual_settings": vs()},
        {"type": "heading", "level": "2", "text": "Today's Top Stories", "anchorHeader": False,
         "anchorIncludeInToc": False, "visual_settings": vs()},
        rss(NEWS_FEED, 4, thumb=True, desc=False),
        {"type": "heading", "level": "2", "text": "What's On", "anchorHeader": False,
         "anchorIncludeInToc": False, "visual_settings": vs()},
        rss(EVENTS_FEED, 4, thumb=True, desc=False),
        {"type": "heading", "level": "2", "text": "Today in Harrow", "anchorHeader": False,
         "anchorIncludeInToc": False, "visual_settings": vs()},
        rss(TODAY_FEED, 1, thumb=False, desc=True, content=True),
        {"type": "button", "text": "Submit Your Event", "href": CONTACT, "alignment": "center",
         "size": "normal", "target": "_blank",
         "visual_settings": {"background_color": RED, "text_color": WHITE}},
    ]
    p = {
        "title": post_title(issue_date),
        "blocks": blocks,
        "status": status,
        "email_settings": {"email_subject_line": SUBJECT, "email_preview_text": PREVIEW,
                           "display_title_in_email": False},
        "web_settings": {"hide_from_feed": bool(segment_id)},
        "social_share": "none",
        "email_capture_type_override": "none",
    }
    if status == "confirmed":
        p["scheduled_at"] = sched
    if segment_id:
        # Test audience: email only to this segment, no web publication targets.
        p["recipients"] = {"email": {"include_segment_ids": [segment_id]}}
    elif full_list:
        p["recipients"] = {"email": {"tier_ids": ["all"]}, "web": {"tier_ids": ["all"]}}
    return p, local, sched


# ---------- feed checks ----------
def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def check_feed(name, url, max_age_days, now):
    """Returns 'ok', 'blocked' (couldn't read; beehiiv may still), or exits on empty/stale."""
    try:
        root = ET.fromstring(fetch(url))
    except urllib.error.HTTPError as e:
        log(f"WARNING: {name} feed returned HTTP {e.code} to this runner (site may block GitHub). Relying on beehiiv's own fetch.")
        return "blocked"
    except Exception as e:
        log(f"WARNING: could not read {name} feed ({type(e).__name__}). Relying on beehiiv's own fetch.")
        return "blocked"
    items = root.findall(".//item")
    if not items:
        fail(f"{name} feed is empty: {url}")
    dates = []
    for it in items:
        t = it.findtext("pubDate")
        try:
            dates.append(email.utils.parsedate_to_datetime(t))
        except Exception:
            pass
    if dates and max_age_days is not None:
        newest = max(dates)
        age = (now - newest).total_seconds() / 86400
        if age > max_age_days:
            fail(f"{name} feed looks stale: newest item is {age:.1f} days old (limit {max_age_days}).")
        log(f"{name} feed OK: {len(items)} items, newest {age:.1f} days old.")
    else:
        log(f"{name} feed OK: {len(items)} items.")
    return "ok"


# ---------- beehiiv API ----------
def api(method, path, key, body=None, params=""):
    url = f"{API}{path}{params}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "today-in-harrow/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read()).get("errors", [])
            detail = "; ".join(f"{d.get('code')}: {d.get('message')}" for d in detail)
        except Exception:
            detail = ""
        hint = {401: "API key missing/invalid", 403: "plan or key scope does not allow this", 429: "rate limited"}.get(e.code, "")
        fail(f"beehiiv {method} {path.split('?')[0]} failed: HTTP {e.code} {hint} {detail}".strip())
    except Exception as e:
        fail(f"beehiiv request failed: {type(e).__name__}")


def already_exists(key, title):
    for page in range(1, 4):
        _, res = api("GET", f"/publications/{PUB_ID}/posts", key,
                     params=f"?status=all&limit=100&page={page}&order_by=created&direction=desc")
        for post in res.get("data", []):
            if post.get("title") == title:
                return post.get("id"), post.get("status")
        if page >= (res.get("total_pages") or 1):
            break
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="default: print payload, no beehiiv calls")
    g.add_argument("--draft", action="store_true", help="create the post as a draft only")
    g.add_argument("--schedule", action="store_true", help="create confirmed post scheduled for 09:00 London")
    ap.add_argument("--today", help="pretend today is YYYY-MM-DD (London), for testing")
    ap.add_argument("--full-list", action="store_true",
                    help="send to the whole list. Required for real scheduling without BEEHIIV_TEST_SEGMENT_ID")
    ap.add_argument("--skip-feed-check", action="store_true")
    a = ap.parse_args()
    mode = "schedule" if a.schedule else "draft" if a.draft else "dry-run"

    now = dt.datetime.now(UTC)
    today = dt.date.fromisoformat(a.today) if a.today else now.astimezone(LONDON).date()
    issue = next_weekday(today)
    segment = os.environ.get("BEEHIIV_TEST_SEGMENT_ID", "").strip() or None
    full_list = a.full_list and not segment

    log(f"Mode: {mode}")
    log(f"Today (London): {today:%A %d %b %Y}. Issue date: {issue:%A %d %b %Y}")

    if mode != "dry-run" and today.weekday() in (4, 5):
        log("Today is Friday or Saturday in London: Monday's issue is created by the Sunday run. Skipping.")
        return 0
    if mode == "schedule" and not segment and not full_list:
        fail("Refusing to schedule to the whole list without --full-list (or set BEEHIIV_TEST_SEGMENT_ID).")

    status = "confirmed" if mode == "schedule" else "draft"
    payload, local, sched = build_payload(issue, status, segment, full_list)
    log(f"Send time: {local:%Y-%m-%d %H:%M %Z} London = {sched} UTC")
    log(f"Audience: {'test segment ' + segment if segment else 'whole list (all tiers)' if full_list else 'beehiiv default (not set)'}")

    if not a.skip_feed_check:
        for name, url, age in (("news", NEWS_FEED, MAX_AGE_DAYS["news"]),
                               ("events", EVENTS_FEED, MAX_AGE_DAYS["events"]),
                               ("today-in-harrow", TODAY_FEED, 2)):
            check_feed(name, url, age, now)

    if mode == "dry-run":
        log("DRY RUN: no request sent to beehiiv. Payload:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    key = os.environ.get("BEEHIIV_API_KEY", "").strip()
    if not key:
        fail("BEEHIIV_API_KEY is not set (add it as a GitHub Actions secret).")
    found = already_exists(key, payload["title"])
    if found:
        log(f"A post titled '{payload['title']}' already exists ({found[0]}, {found[1]}). Nothing to do.")
        return 0
    _, res = api("POST", f"/publications/{PUB_ID}/posts", key, body=payload)
    pid = (res.get("data") or {}).get("id")
    if not pid:
        fail("beehiiv did not return a post id.")
    d = res.get("data") or {}
    log(f"beehiiv returned: id={pid} title={d.get('title')!r} status={d.get('status')} web_url={d.get('web_url')} scheduled_at={d.get('scheduled_at')}")
    log(f"Created post {pid} as {status}" + (f", scheduled for {sched}" if status == "confirmed" else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
