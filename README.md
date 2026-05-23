# Existarr

Your media collection, cross-referenced with TVDB. Existarr shows only the episodes you actually own — nothing more.

---

## Setup

### 1. Configure `docker-compose.yml`

Open `docker-compose.yml` and update two lines:

```yaml
- TVDB_API_KEY=your_api_key_here        # Your TVDB v4 API key
- /path/to/your/media:/media:ro         # Absolute path to your media root
```

Your TVDB API key can be found at https://thetvdb.com/dashboard/account/apikey

### 2. Build and run

```bash
docker compose up -d
```

### 3. Open the app

Navigate to http://localhost:5100

---

## Adding a show

1. Find the series on TVDB (e.g. `https://thetvdb.com/series/pbs-nature` → the numeric ID is in the URL or on the series page)
2. Paste the numeric ID into the sidebar input and click **+ ADD**

---

## Media structure

Existarr expects your files to follow Plex-style naming with `SxxExx` episode codes anywhere in the filename:

```
/media
  PBS Nature/
    Season 01/
      PBS.Nature.S01E01.Something.mkv
    Season 02/
      ...
  NOVA/
    Season 43/
      NOVA.S43E01.Something.mkv
```

The scanner walks all subdirectories under `MEDIA_ROOT`, so exact folder depth doesn't matter as long as `SxxExx` appears in the filename.

---

## Keyword search

The search bar on each series page filters in real-time against:
- Episode title
- Plot summary

Matching text is highlighted in the results.

---

## Data persistence

Added shows are stored in a named Docker volume (`existarr_data`) so they survive container restarts and rebuilds.
