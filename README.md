# Existarr

Your media collection, cross-referenced with TVDB. Existarr shows only the episodes and movies you actually own — nothing more.

This project was born from a home schooling need. We love watching documentaries to supplement our learning, but were never sure what we actually had. This project helps us to know what is in our inventory and search across all series and films. With this project we can search for keywords and display all options before choosing what to watch.

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

## Adding your media
**There are two ways to add your media to Existarr**
1. Manually adding each show or movie by clicking +ADD MANUALLY at any page
2. Scrape your existing directories for matches by clicking ⟳Auto-Discovery

**Adding via Auto-Discovery**
1. Click the ⟳Auto-Discovery button on the left pane.
2. Add the path (definied in your docker compose) to your media.
3. Select whether the file path you have chosen contains Movies or Series (this is crucial for proper scraping).
4. Click Add Source, then Scan Now. The scan process will take a few seconds to run, then will display all added content.

**Manually Adding content**
1. Find the series on TVDB (e.g. `https://thetvdb.com/series/pbs-nature` → the numeric ID is in the General Information of the series page, listed as TheTVDB.com Series ID)
2. Paste the numeric ID into the sidebar input
3. Add the path to that media and click **+ ADD**

---

## Media structure

Existarr expects your files to follow Plex-style naming with `SxxExx` episode codes anywhere in the filename. It is also imperative that the TVDB numerical ID appear in your directory name:

```
/media
  Movies/
    Documentaries You Own (2026) {tvdb-xxxxxx}/
      Documentaries You Own (2026) {tvdb-xxxxxx}.mp4
  Series/
    Nature (1982) {tvdb-81157}/
      Season 44/
        S44E01 Something.mkv
    NOVA (1974) {tvdb-76119}/
      Season 43/
        S43E01 Something.mkv
```

The scanner walks all subdirectories under `MEDIA_ROOT`, so exact folder depth doesn't matter as long as `SxxExx` appears in the filename.

---

## Keyword search

The search bar on each series page filters in real-time against:
- Episode title
- Plot summary

Matching text is highlighted in the results.
That said, it functions on text strings. So check for any irrelevant results.
---
(this is a 100% vibe coded project)
