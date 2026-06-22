# Signal Brief

A static, source-first dashboard for public defense-industry news and recent Department of Defense award records. It is designed for GitHub Pages: no visitor API keys, backend, database, or build step required.

## What it does

- Aggregates focused public news searches from Google News RSS.
- Pulls recent DoD award records from the public USAspending API.
- Ranks headlines with a transparent keyword, entity, source, and freshness score.
- Supports category filters, search, sorting, and a locally saved company watchlist.
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
