# Local-First Storage

YOUTUBE AI AGENT is designed to keep data on the Mac by default.

## Rules

- Store raw downloads, reports, screenshots, graphs, cache files, and backups under `storage/`.
- Read from local files first before making a network request.
- Download external data only when a collector, report, or AI workflow needs fresh input.
- Keep long-lived records in PostgreSQL, but treat the Mac filesystem as the primary working store for artifacts.

## Suggested environment values

- `STORAGE_ROOT=/Users/mayankk996/Patrix Gaming/YOUTUBE AI AGENT/storage`
- `PREFER_LOCAL_STORAGE=true`
- `DOWNLOAD_ONLY_WHEN_NEEDED=true`
