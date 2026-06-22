#!/usr/bin/env python3
"""Build the static Signal Brief dataset from public news feeds and USAspending."""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "news.json"
USER_AGENT = "SignalBrief/1.0 (+https://github.com/; public-interest research dashboard)"

FEEDS = {
    "contracts": '"defense contract" OR "Pentagon award" OR "DoD contract"',
    "companies": 'Lockheed OR RTX OR Raytheon OR Northrop OR "General Dynamics" OR "Boeing Defense"',
    "technology": '"defense technology" OR hypersonic OR drone OR missile OR autonomous military',
    "policy": 'Pentagon budget OR defense authorization OR arms export OR defense acquisition',
    "space": '"Space Force" OR military satellite OR missile warning satellite',
    "cyber": 'Pentagon cybersecurity OR "defense cyber" OR CMMC',
}

ENTITIES = {
    "Lockheed Martin": ("lockheed", "f-35", "f35"),
    "RTX": ("rtx", "raytheon", "pratt & whitney"),
    "Northrop Grumman": ("northrop", "b-21", "sentinel icbm"),
    "General Dynamics": ("general dynamics", "gulfstream", "electric boat"),
    "Boeing": ("boeing", "kc-46", "f-15ex"),
    "L3Harris": ("l3harris", "l3 harris"),
    "BAE Systems": ("bae systems",),
    "SpaceX": ("spacex", "starshield"),
    "Palantir": ("palantir",),
    "Anduril": ("anduril",),
}

MATERIAL_TERMS = {
    "contract": 12, "award": 11, "selected": 8, "production": 8,
    "acquisition": 8, "budget": 7, "procurement": 9, "order": 6,
    "protest": 8, "export": 7, "delivery": 6, "funding": 6,
    "missile": 5, "satellite": 5, "pentagon": 5, "department of defense": 6,
}

SOURCE_WEIGHT = {
    "defense.gov": 10, "reuters": 9, "associated press": 8, "gao": 9,
    "breaking defense": 7, "defense news": 7, "janes": 7, "space news": 6,
    "c4isrnet": 6, "air & space forces": 6, "naval news": 6,
}

CATEGORY_CONTEXT = {
    "contracts": "Why it matters: award activity can reveal program momentum, revenue timing, and shifts in contractor backlog.",
    "companies": "Why it matters: this may change competitive positioning, execution risk, or expectations across the defense supply chain.",
    "technology": "Why it matters: emerging capabilities can redirect procurement priorities and reshape the program landscape.",
    "policy": "Why it matters: policy and budget decisions set the demand environment for defense programs and suppliers.",
    "space": "Why it matters: space architecture is an expanding layer of communications, sensing, and missile-warning investment.",
    "cyber": "Why it matters: cyber requirements increasingly affect contract eligibility, program risk, and supplier compliance costs.",
}


def request(url: str, *, data: bytes | None = None, timeout: int = 30) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json, application/xml, text/xml, */*"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def strip_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", html.unescape(value or ""))
    return re.sub(r"\s+", " ", value).strip()


def canonical_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def parse_feed(category: str, query: str) -> list[dict]:
    params = urllib.parse.urlencode({"q": f"({query}) when:10d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
    raw = request(f"https://news.google.com/rss/search?{params}")
    root = ET.fromstring(raw)
    output = []
    for item in root.findall("./channel/item"):
        raw_title = strip_html(item.findtext("title", ""))
        source_node = item.find("source")
        source = strip_html(source_node.text if source_node is not None else "Unknown source")
        suffix = f" - {source}"
        title = raw_title[:-len(suffix)] if source and raw_title.endswith(suffix) else raw_title
        if not title:
            continue
        try:
            published = parsedate_to_datetime(item.findtext("pubDate", "")).astimezone(timezone.utc)
        except (TypeError, ValueError):
            published = datetime.now(timezone.utc)
        description = strip_html(item.findtext("description", ""))
        if description.lower().startswith(title.lower()):
            description = CATEGORY_CONTEXT[category]
        text = f"{title} {description} {source}".lower()
        tags = [name for name, terms in ENTITIES.items() if any(term in text for term in terms)]
        score = 44
        score += sum(weight for term, weight in MATERIAL_TERMS.items() if term in text)
        score += sum(weight for key, weight in SOURCE_WEIGHT.items() if key in source.lower())
        score += min(len(tags) * 3, 9)
        age_hours = max(0, (datetime.now(timezone.utc) - published).total_seconds() / 3600)
        score += max(0, round(8 - age_hours / 30))
        score = min(99, max(48, score))
        output.append({
            "id": hashlib.sha1(f"{title}{source}".encode()).hexdigest()[:12],
            "title": title,
            "summary": description[:360],
            "url": item.findtext("link", ""),
            "source": source,
            "published": published.isoformat().replace("+00:00", "Z"),
            "category": category,
            "score": score,
            "tags": tags[:3] or [category.title()],
        })
    return output


def fetch_articles() -> list[dict]:
    articles: list[dict] = []
    for category, query in FEEDS.items():
        try:
            articles.extend(parse_feed(category, query))
            time.sleep(0.25)
        except (urllib.error.URLError, ET.ParseError, TimeoutError) as error:
            print(f"Warning: {category} feed failed: {error}", file=sys.stderr)
    deduped: dict[str, dict] = {}
    for article in articles:
        key = canonical_title(article["title"])
        if key not in deduped or article["score"] > deduped[key]["score"]:
            deduped[key] = article
    return sorted(deduped.values(), key=lambda item: (item["score"], item["published"]), reverse=True)[:48]


def fetch_contracts() -> list[dict]:
    today = datetime.now(timezone.utc).date()
    payload = {
        "filters": {
            "time_period": [{"start_date": str(today - timedelta(days=45)), "end_date": str(today)}],
            "award_type_codes": ["A", "B", "C", "D"],
            "agencies": [{"type": "awarding", "tier": "toptier", "name": "Department of Defense"}],
        },
        "fields": ["Award ID", "Recipient Name", "Award Amount", "Description", "Awarding Agency", "Start Date"],
        "page": 1,
        "limit": 12,
        "sort": "Award Amount",
        "order": "desc",
    }
    raw = request(
        "https://api.usaspending.gov/api/v2/search/spending_by_award/",
        data=json.dumps(payload).encode(),
    )
    results = json.loads(raw).get("results", [])
    contracts = []
    for item in results:
        award_id = item.get("Award ID", "Public record")
        generated = item.get("generated_internal_id", "")
        contracts.append({
            "award_id": award_id,
            "recipient": item.get("Recipient Name") or "Recipient not listed",
            "amount": item.get("Award Amount") or 0,
            "description": (item.get("Description") or "Description not available").strip().capitalize(),
            "agency": item.get("Awarding Agency") or "Department of Defense",
            "date": item.get("Start Date", ""),
            "url": f"https://www.usaspending.gov/award/{urllib.parse.quote(generated)}" if generated else "https://www.usaspending.gov/search",
        })
    return contracts


def main() -> int:
    old_data = {}
    if OUTPUT.exists():
        try:
            old_data = json.loads(OUTPUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    articles = fetch_articles()
    if not articles:
        articles = old_data.get("articles", [])
    try:
        contracts = fetch_contracts()
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as error:
        print(f"Warning: USAspending API failed: {error}", file=sys.stderr)
        contracts = old_data.get("contracts", [])

    if not articles:
        raise RuntimeError("Collector produced no articles and no prior snapshot exists")

    output = {
        "meta": {
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "article_count": len(articles),
            "contract_count": len(contracts),
            "sources": ["Google News RSS", "USAspending API"],
            "method": "Public-source collection with deterministic topical relevance scoring",
        },
        "articles": articles,
        "contracts": contracts,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(articles)} articles and {len(contracts)} contracts to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
