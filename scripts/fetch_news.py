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

FEEDS = [
    {"category": "companies", "region": "North America", "gl": "US", "days": 14, "query": '(Lockheed OR RTX OR Northrop OR "General Dynamics") defense'},
    {"category": "companies", "region": "North America", "gl": "US", "days": 14, "query": '("Boeing Defense" OR L3Harris OR Anduril OR Palantir) defense'},
    {"category": "companies", "region": "Europe", "gl": "GB", "days": 30, "query": '("BAE Systems" OR Thales OR QinetiQ) defense'},
    {"category": "companies", "region": "Europe", "gl": "FR", "days": 30, "query": 'ChapsVision defense'},
    {"category": "companies", "region": "Europe", "gl": "GB", "days": 30, "query": '(Rheinmetall OR Leonardo OR Hensoldt OR KNDS) defense'},
    {"category": "companies", "region": "Europe", "gl": "FR", "days": 30, "query": '(Saab OR "Airbus Defence" OR Dassault OR MBDA OR "Naval Group") defense'},
    {"category": "companies", "region": "Europe", "gl": "IT", "days": 30, "query": '(Fincantieri OR Indra OR "Leonardo DRS") defense'},
    {"category": "companies", "region": "Middle East", "gl": "IL", "days": 30, "query": '("Elbit Systems" OR "Israel Aerospace Industries" OR "Rafael Advanced Defense") defense'},
    {"category": "companies", "region": "Middle East", "gl": "AE", "days": 30, "query": '"EDGE Group" defense'},
    {"category": "companies", "region": "Asia-Pacific", "gl": "AU", "days": 30, "query": '("Hanwha Aerospace" OR "Mitsubishi Heavy Industries" OR "HD Hyundai Heavy") defense'},
    {"category": "companies", "region": "Asia-Pacific", "gl": "AU", "days": 30, "query": '("ST Engineering" OR Austal OR "Hindustan Aeronautics" OR "Bharat Dynamics") defense'},
    {"category": "contracts", "region": "Global", "gl": "GB", "days": 10, "query": 'international "defence contract" OR "defense contract" OR military procurement award'},
    {"category": "technology", "region": "Global", "gl": "GB", "days": 10, "query": '"defence technology" OR "defense technology" OR hypersonic OR counter-drone OR autonomous military'},
    {"category": "policy", "region": "Global", "gl": "GB", "days": 10, "query": 'NATO defense budget OR European defence procurement OR arms export OR military acquisition'},
    {"category": "space", "region": "Global", "gl": "GB", "days": 10, "query": 'military satellite OR missile warning satellite OR sovereign space defense'},
    {"category": "cyber", "region": "Global", "gl": "GB", "days": 10, "query": 'defense cybersecurity OR defence cyber contract OR military cyber procurement'},
]

ENTITIES = {
    "Lockheed Martin": ("lockheed", "f-35", "f35"),
    "RTX": ("rtx", "raytheon", "pratt & whitney"),
    "Northrop Grumman": ("northrop", "b-21", "sentinel icbm"),
    "General Dynamics": ("general dynamics", "gulfstream", "electric boat"),
    "Boeing": ("boeing", "kc-46", "f-15ex"),
    "L3Harris": ("l3harris", "l3 harris"),
    "BAE Systems": ("bae systems",),
    "ChapsVision": ("chapsvision",),
    "Thales": ("thales",),
    "Rheinmetall": ("rheinmetall",),
    "Leonardo": ("leonardo spa", "leonardo drs", "leonardo d.r.s", "leonardo defense", "leonardo defence"),
    "Saab": ("saab", "gripen"),
    "Airbus Defence": ("airbus defence", "airbus defense"),
    "Dassault Aviation": ("dassault", "rafale"),
    "MBDA": ("mbda",),
    "KNDS": ("knds",),
    "Naval Group": ("naval group",),
    "Hensoldt": ("hensoldt",),
    "QinetiQ": ("qinetiq",),
    "Fincantieri": ("fincantieri",),
    "Elbit Systems": ("elbit",),
    "Israel Aerospace Industries": ("israel aerospace industries", "iai "),
    "Rafael": ("rafael advanced defense", "rafael advanced defence"),
    "EDGE Group": ("edge group",),
    "Hanwha Aerospace": ("hanwha aerospace", "hanwha defense", "hanwha defence"),
    "Mitsubishi Heavy Industries": ("mitsubishi heavy industries",),
    "ST Engineering": ("st engineering",),
    "Austal": ("austal",),
    "Hindustan Aeronautics": ("hindustan aeronautics",),
    "Bharat Dynamics": ("bharat dynamics",),
    "SpaceX": ("spacex", "starshield"),
    "Palantir": ("palantir",),
    "Anduril": ("anduril",),
}

ENTITY_REGIONS = {
    "Lockheed Martin": "North America", "RTX": "North America", "Northrop Grumman": "North America",
    "General Dynamics": "North America", "Boeing": "North America", "L3Harris": "North America",
    "SpaceX": "North America", "Palantir": "North America", "Anduril": "North America",
    "BAE Systems": "Europe", "ChapsVision": "Europe", "Thales": "Europe", "Rheinmetall": "Europe",
    "Leonardo": "Europe", "Saab": "Europe", "Airbus Defence": "Europe", "Dassault Aviation": "Europe",
    "MBDA": "Europe", "KNDS": "Europe", "Naval Group": "Europe", "Hensoldt": "Europe",
    "QinetiQ": "Europe", "Fincantieri": "Europe",
    "Elbit Systems": "Middle East", "Israel Aerospace Industries": "Middle East", "Rafael": "Middle East",
    "EDGE Group": "Middle East",
    "Hanwha Aerospace": "Asia-Pacific", "Mitsubishi Heavy Industries": "Asia-Pacific",
    "ST Engineering": "Asia-Pacific", "Austal": "Asia-Pacific", "Hindustan Aeronautics": "Asia-Pacific",
    "Bharat Dynamics": "Asia-Pacific",
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
    "shephard": 6, "army technology": 5, "european defence review": 6,
    "defence connect": 6, "israel defense": 6, "asian military review": 6,
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


def parse_feed(category: str, query: str, region: str, gl: str, days: int = 10) -> list[dict]:
    params = urllib.parse.urlencode({"q": f"({query}) when:{days}d", "hl": "en", "gl": gl, "ceid": f"{gl}:en"})
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
        entity_regions = [ENTITY_REGIONS[tag] for tag in tags if tag in ENTITY_REGIONS]
        if region != "Global" and region in entity_regions:
            article_region = region
        else:
            article_region = max(set(entity_regions), key=entity_regions.count) if entity_regions else region
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
            "region": article_region,
            "score": score,
            "tags": tags[:3] or [category.title()],
        })
    return output


def fetch_articles() -> list[dict]:
    articles: list[dict] = []
    for feed in FEEDS:
        try:
            articles.extend(parse_feed(feed["category"], feed["query"], feed["region"], feed["gl"], feed.get("days", 10)))
            time.sleep(0.25)
        except (urllib.error.URLError, ET.ParseError, TimeoutError) as error:
            print(f"Warning: {feed['region']} {feed['category']} feed failed: {error}", file=sys.stderr)
    deduped: dict[str, dict] = {}
    for article in articles:
        key = canonical_title(article["title"])
        existing = deduped.get(key)
        if existing and existing["region"] == "Global" and article["region"] != "Global":
            existing["region"] = article["region"]
            existing["tags"] = list(dict.fromkeys(existing["tags"] + article["tags"]))[:3]
        if key not in deduped or article["score"] > deduped[key]["score"]:
            if existing and existing["region"] != "Global" and article["region"] == "Global":
                article["region"] = existing["region"]
                article["tags"] = list(dict.fromkeys(existing["tags"] + article["tags"]))[:3]
            deduped[key] = article
    ranked = sorted(deduped.values(), key=lambda item: (item["score"], item["published"]), reverse=True)
    # Keep the company universe genuinely plural, then reserve space for each market.
    selected: list[dict] = []
    selected_ids: set[str] = set()
    priority_entities = (
        "BAE Systems", "ChapsVision", "Rheinmetall", "Leonardo", "Thales",
        "Elbit Systems", "Israel Aerospace Industries", "Rafael", "EDGE Group",
        "Hanwha Aerospace", "Mitsubishi Heavy Industries", "ST Engineering", "Austal",
        "Lockheed Martin", "RTX", "Northrop Grumman", "General Dynamics",
    )
    for entity in priority_entities:
        article = next((item for item in ranked if entity in item["tags"] and item["id"] not in selected_ids), None)
        if article:
            selected.append(article)
            selected_ids.add(article["id"])
    for region, quota in (("Europe", 14), ("Middle East", 10), ("Asia-Pacific", 10), ("North America", 14), ("Global", 10)):
        added = 0
        for article in (item for item in ranked if item["region"] == region):
            if article["id"] in selected_ids:
                continue
            selected.append(article)
            selected_ids.add(article["id"])
            added += 1
            if added == quota:
                break
    selected.extend(item for item in ranked if item["id"] not in selected_ids)
    return sorted(selected[:72], key=lambda item: (item["score"], item["published"]), reverse=True)


def fetch_us_contracts() -> list[dict]:
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
            "currency": "USD",
            "description": (item.get("Description") or "Description not available").strip().capitalize(),
            "agency": item.get("Awarding Agency") or "Department of Defense",
            "jurisdiction": "United States",
            "record_source": "USAspending",
            "date": item.get("Start Date", ""),
            "url": f"https://www.usaspending.gov/award/{urllib.parse.quote(generated)}" if generated else "https://www.usaspending.gov/search",
        })
    return contracts


def fetch_uk_contracts() -> list[dict]:
    """Collect recent UK defence awards from the Contracts Finder OCDS feed."""
    published_to = None
    matches: list[dict] = []
    seen: set[str] = set()
    defence_buyers = ("ministry of defence", "defence science and technology laboratory", "awe plc")
    defence_terms = ("defence", "defense", "military", "naval", "warship", "weapon", "ammunition", "missile", "aircraft", "army", "royal air force", "royal navy")

    for _ in range(6):
        params = {"limit": 100}
        if published_to:
            params["publishedTo"] = published_to
        url = "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search?" + urllib.parse.urlencode(params)
        releases = json.loads(request(url)).get("releases", [])
        if not releases:
            break
        for release in releases:
            awards = release.get("awards") or []
            tender = release.get("tender") or {}
            buyer = (release.get("buyer") or {}).get("name", "")
            text = f"{buyer} {tender.get('title', '')} {tender.get('description', '')}".lower()
            cpv = str((tender.get("classification") or {}).get("id", ""))
            relevant = any(name in buyer.lower() for name in defence_buyers) or cpv.startswith("35") or any(term in text for term in defence_terms)
            if not awards or not relevant:
                continue
            award = awards[0]
            suppliers = award.get("suppliers") or []
            supplier = suppliers[0].get("name") if suppliers else "Supplier not listed"
            award_id = release.get("ocid") or release.get("id") or "UK public record"
            if award_id in seen:
                continue
            seen.add(award_id)
            value = award.get("value") or tender.get("value") or {}
            documents = award.get("documents") or tender.get("documents") or []
            document_url = next((doc.get("url") for doc in documents if doc.get("url")), "https://www.contractsfinder.service.gov.uk/Search")
            matches.append({
                "award_id": award_id,
                "recipient": supplier,
                "amount": value.get("amount") or 0,
                "currency": value.get("currency") or "GBP",
                "description": (tender.get("title") or tender.get("description") or "UK defence procurement record").strip(),
                "agency": buyer or "UK public buyer",
                "jurisdiction": "United Kingdom",
                "record_source": "Contracts Finder",
                "date": award.get("datePublished") or award.get("date") or release.get("date", ""),
                "url": document_url,
            })
        oldest = releases[-1].get("date")
        if not oldest:
            break
        try:
            cursor = datetime.fromisoformat(oldest.replace("Z", "+00:00")) - timedelta(seconds=1)
            published_to = cursor.isoformat()
        except ValueError:
            break
        if len(matches) >= 8:
            break
    return sorted(matches, key=lambda item: item.get("date", ""), reverse=True)[:8]


def fetch_contracts() -> list[dict]:
    contracts: list[dict] = []
    errors = []
    try:
        contracts.extend(fetch_us_contracts()[:8])
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as error:
        errors.append(f"USAspending: {error}")
    try:
        contracts.extend(fetch_uk_contracts())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as error:
        errors.append(f"Contracts Finder: {error}")
    for error in errors:
        print(f"Warning: {error}", file=sys.stderr)
    return sorted(contracts, key=lambda item: item.get("date", ""), reverse=True)


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
    contracts = fetch_contracts()
    if not contracts:
        contracts = old_data.get("contracts", [])

    if not articles:
        raise RuntimeError("Collector produced no articles and no prior snapshot exists")

    output = {
        "meta": {
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "article_count": len(articles),
            "contract_count": len(contracts),
            "sources": ["Regional Google News RSS editions", "USAspending API", "UK Contracts Finder OCDS API"],
            "regions": sorted({item.get("region", "Global") for item in articles}),
            "method": "Region-balanced public-source collection with deterministic topical relevance scoring",
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
