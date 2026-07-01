# YOUTUBE AI AGENT

YOUTUBE AI AGENT is a YouTube analytics, game-news scraping, and AI recommendation workspace.

The project is local-first: keep raw data, reports, caches, and generated assets on your Mac under `storage/` unless a module explicitly needs a fresh download.

## What this scaffold includes

- YouTube analytics collection and reporting
- News and trend scraping for game-related updates
- AI-powered video suggestions and idea generation
- PostgreSQL-ready database layout
- API, reports, notifications, and dashboard folders

## Next steps

1. Add API keys and database settings to `.env`.
2. Set `STORAGE_ROOT` to a local path on your Mac and keep `PREFER_LOCAL_STORAGE=true`.
3. Implement collectors for YouTube, news, RSS, and competitors so they download data only when needed.
4. Wire analytics and AI recommendation flows into the scheduler.
