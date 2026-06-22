# Signal Brief

A static, source-first dashboard for global defense-industry news and public government award records. It is designed for GitHub Pages: no visitor API keys, backend, database, or build step required.

## What it does

- Aggregates dedicated regional news searches for Europe, the Middle East, Asia-Pacific, North America, and cross-border developments.
- Tracks global primes and challengers including BAE Systems, ChapsVision, Elbit Systems, Rheinmetall, Leonardo, Hanwha Aerospace, Lockheed Martin, and others.
- Pulls recent public records from the USAspending and UK Contracts Finder APIs, with jurisdiction and currency kept explicit.
- Ranks headlines with transparent entity, material-event, source, freshness, and regional-balance rules.
- Supports market and category filters, search, sorting, and a locally saved company watchlist.
- Refreshes the committed JSON snapshot every six hours with GitHub Actions.

## Run locally

```bash
python scripts/fetch_news.py
python -m http.server 8000
```

Open `http://localhost:8000`.

## Publish on GitHub Pages

In the repository settings, open **Pages** and select **GitHub Actions** as the source. Push the default branch or run **Deploy Signal Brief to Pages** manually. Run **Refresh public intelligence** once to confirm that Actions has write permission.

## Data note

Signal Brief is a research interface, not investment advice. Public records can be incomplete, delayed, duplicated, or revised. Always verify material facts at the linked source.
