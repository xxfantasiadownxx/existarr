import os
import json
import re
import logging
import requests
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)

TVDB_API_KEY = os.environ.get("TVDB_API_KEY", "")
TVDB_BASE    = "https://api4.thetvdb.com/v4"
DATA_FILE    = "/data/shows.json"
SOURCES_FILE = "/data/sources.json"

TVDB_ID_RE = re.compile(r"\{tvdb-(\d+)\}", re.IGNORECASE)
SXEX_RE    = re.compile(r"[Ss](\d{1,2})[Ee](\d{1,2})")
MEDIA_ROOT = os.environ.get("MEDIA_ROOT", "/media")

# ── TVDB helpers ──────────────────────────────────────────────────────────────

def tvdb_token():
    r = requests.post(f"{TVDB_BASE}/login", json={"apikey": TVDB_API_KEY}, timeout=15)
    r.raise_for_status()
    return r.json()["data"]["token"]

def tvdb_get(path, token):
    r = requests.get(
        f"{TVDB_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("data", {})

# ── Episode helpers ───────────────────────────────────────────────────────────

def get_all_episodes(tvdb_id, token):
    episodes_raw = []
    page = 0
    while True:
        data  = tvdb_get(f"/series/{tvdb_id}/episodes/official?page={page}", token)
        batch = data.get("episodes", []) if isinstance(data, dict) else []
        if not batch:
            break
        episodes_raw.extend(batch)
        page += 1
        if len(batch) < 100:
            break
    return episodes_raw

def filter_to_owned(episodes_raw, owned):
    episodes = []
    for ep in episodes_raw:
        s = ep.get("seasonNumber")
        e = ep.get("number")
        if s is None or e is None:
            continue
        if (int(s), int(e)) not in owned:
            continue
        episodes.append({
            "season":   int(s),
            "episode":  int(e),
            "title":    ep.get("name") or "Untitled",
            "overview": ep.get("overview") or "",
            "aired":    ep.get("aired") or "",
            "runtime":  ep.get("runtime") or "",
        })
    episodes.sort(key=lambda x: (x["season"], x["episode"]))
    return episodes

# ── Filesystem helpers ────────────────────────────────────────────────────────

def scan_media(paths):
    """
    Scan a list of absolute paths and return a unified set of
    (season, episode) int tuples found across all of them.
    """
    owned = set()
    for path in paths:
        if not os.path.isdir(path):
            log.warning("scan_media: path not found: %s", path)
            continue
        for dirpath, _, filenames in os.walk(path):
            for fname in filenames:
                m = SXEX_RE.search(fname)
                if m:
                    owned.add((int(m.group(1)), int(m.group(2))))
    return owned

def resolve_path(raw):
    """
    Turn a user-supplied path string into an absolute path.
    - Already absolute -> use as-is
    - Relative         -> join onto MEDIA_ROOT
    """
    raw = raw.strip()
    if not raw:
        return None
    if os.path.isabs(raw):
        return raw
    return os.path.join(MEDIA_ROOT, raw)

def get_media_paths(show):
    """
    Return resolved absolute media paths for a show.
    Handles both new media_paths list and legacy media_path string.
    Relative paths are resolved against MEDIA_ROOT.
    """
    if "media_paths" in show:
        raw_list = show["media_paths"]
    elif "media_path" in show:
        raw_list = [show["media_path"]]
    else:
        raw_list = []

    resolved = [resolve_path(p) for p in raw_list]
    return [p for p in resolved if p]

# ── Persistence ───────────────────────────────────────────────────────────────

def load_shows():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {}

def save_shows(shows):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(shows, f, indent=2)

def load_sources():
    """Load auto-discovery source paths."""
    if os.path.exists(SOURCES_FILE):
        with open(SOURCES_FILE) as f:
            return json.load(f)
    return {"paths": [], "last_run": None, "last_added": []}

def save_sources(sources):
    os.makedirs(os.path.dirname(SOURCES_FILE), exist_ok=True)
    with open(SOURCES_FILE, "w") as f:
        json.dump(sources, f, indent=2)

# ── Auto-discovery ────────────────────────────────────────────────────────────

def discover_tvdb_folders(root_paths):
    """
    Recursively walk root_paths and return list of
    {"tvdb_id": str, "path": str, "folder_name": str}
    for every folder whose name contains {tvdb-XXXXXXX}.
    """
    found = []
    for root in root_paths:
        if not os.path.isdir(root):
            log.warning("discover: source path not found: %s", root)
            continue
        for dirpath, dirnames, _ in os.walk(root):
            for d in dirnames:
                m = TVDB_ID_RE.search(d)
                if m:
                    found.append({
                        "tvdb_id":     m.group(1),
                        "path":        os.path.join(dirpath, d),
                        "folder_name": d,
                    })
    return found

def run_autodiscovery():
    """
    Scan all source paths, find {tvdb-ID} folders, add any new shows.
    Returns list of newly-added show names.
    """
    sources = load_sources()
    if not sources.get("paths"):
        log.info("autodiscovery: no source paths configured, skipping.")
        return []

    log.info("autodiscovery: starting scan of %d source(s)…", len(sources["paths"]))
    found   = discover_tvdb_folders(sources["paths"])
    shows   = load_shows()
    added   = []

    if not found:
        log.info("autodiscovery: no {tvdb-ID} folders found.")
    else:
        try:
            token = tvdb_token()
        except Exception as e:
            log.error("autodiscovery: TVDB auth failed: %s", e)
            sources["last_run"] = datetime.now().isoformat()
            save_sources(sources)
            return []

        for item in found:
            tvdb_id = item["tvdb_id"]

            if tvdb_id in shows:
                # Already known — ensure this path is in its media_paths list
                existing_paths = get_media_paths(shows[tvdb_id])
                if item["path"] not in existing_paths:
                    existing_paths.append(item["path"])
                    shows[tvdb_id]["media_paths"] = existing_paths
                    shows[tvdb_id].pop("media_path", None)
                continue

            # New show — fetch from TVDB and add
            try:
                series = tvdb_get(f"/series/{tvdb_id}", token)
                shows[tvdb_id] = {
                    "id":          tvdb_id,
                    "name":        series.get("name", item["folder_name"]),
                    "image":       series.get("image", ""),
                    "media_paths": [item["path"]],
                    "auto":        True,
                }
                added.append(series.get("name", item["folder_name"]))
                log.info("autodiscovery: added '%s' (tvdb %s)", shows[tvdb_id]["name"], tvdb_id)
            except Exception as e:
                log.error("autodiscovery: failed to add tvdb %s: %s", tvdb_id, e)

    save_shows(shows)
    sources["last_run"]   = datetime.now().isoformat()
    sources["last_added"] = added
    save_sources(sources)
    log.info("autodiscovery: done. %d new show(s) added.", len(added))
    return added

# ── Scheduler ─────────────────────────────────────────────────────────────────

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(run_autodiscovery, "interval", hours=24, id="autodiscovery")
scheduler.start()
# Run once at startup (in a thread so Flask starts immediately)
import threading
threading.Thread(target=run_autodiscovery, daemon=True).start()

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", shows=load_shows())


@app.route("/add", methods=["POST"])
def add_show():
    tvdb_id = request.form.get("tvdb_id", "").strip()
    # Collect all path fields (path_0, path_1, …)
    paths = [
        v.strip()
        for k, v in request.form.items()
        if k.startswith("path_") and v.strip()
    ]

    if not tvdb_id.isdigit():
        return redirect(url_for("index"))

    shows = load_shows()
    if tvdb_id not in shows:
        try:
            token  = tvdb_token()
            series = tvdb_get(f"/series/{tvdb_id}", token)
            shows[tvdb_id] = {
                "id":          tvdb_id,
                "name":        series.get("name", f"Series {tvdb_id}"),
                "image":       series.get("image", ""),
                "media_paths": paths,
                "auto":        False,
            }
            save_shows(shows)
        except Exception as e:
            return f"Error adding show: {e}", 500

    return redirect(url_for("show_series", tvdb_id=tvdb_id))


@app.route("/remove/<tvdb_id>", methods=["POST"])
def remove_show(tvdb_id):
    shows = load_shows()
    shows.pop(tvdb_id, None)
    save_shows(shows)
    return redirect(url_for("index"))


@app.route("/update-paths/<tvdb_id>", methods=["POST"])
def update_paths(tvdb_id):
    shows = load_shows()
    if tvdb_id in shows:
        paths = [
            v.strip()
            for k, v in request.form.items()
            if k.startswith("path_") and v.strip()
        ]
        shows[tvdb_id]["media_paths"] = paths
        shows[tvdb_id].pop("media_path", None)   # remove legacy key if present
        save_shows(shows)
    return redirect(url_for("show_series", tvdb_id=tvdb_id))


@app.route("/series/<tvdb_id>")
def show_series(tvdb_id):
    shows = load_shows()
    show  = shows.get(tvdb_id)
    if not show:
        return redirect(url_for("index"))

    try:
        token        = tvdb_token()
        series_data  = tvdb_get(f"/series/{tvdb_id}/extended", token)
        show_name    = series_data.get("name", show["name"])
        show_image   = series_data.get("image", show.get("image", ""))
        episodes_raw = get_all_episodes(tvdb_id, token)
    except Exception as e:
        return f"Error fetching series data from TVDB: {e}", 500

    media_paths = get_media_paths(show)
    owned       = scan_media(media_paths)
    episodes    = filter_to_owned(episodes_raw, owned)

    return render_template(
        "series.html",
        show=show,
        show_name=show_name,
        show_image=show_image,
        episodes=episodes,
        shows=shows,
        tvdb_id=tvdb_id,
        media_paths=media_paths,
    )


@app.route("/search")
def global_search():
    query  = request.args.get("q", "").strip()
    shows  = load_shows()
    results = []

    if query:
        q = query.lower()
        try:
            token = tvdb_token()
            for tvdb_id, show in shows.items():
                episodes_raw = get_all_episodes(tvdb_id, token)
                owned        = scan_media(get_media_paths(show))
                owned_eps    = filter_to_owned(episodes_raw, owned)
                matched = [
                    ep for ep in owned_eps
                    if q in ep["title"].lower() or q in ep["overview"].lower()
                ]
                if matched:
                    results.append({
                        "tvdb_id":    tvdb_id,
                        "show_name":  show["name"],
                        "show_image": show.get("image", ""),
                        "episodes":   matched,
                    })
        except Exception as e:
            return f"Search error: {e}", 500

    return render_template(
        "search.html",
        shows=shows,
        query=query,
        results=results,
        total=sum(len(r["episodes"]) for r in results),
    )


# ── Auto-discovery management routes ─────────────────────────────────────────

@app.route("/sources")
def sources_page():
    return render_template("sources.html", shows=load_shows(), sources=load_sources())

@app.route("/sources/add", methods=["POST"])
def add_source():
    path = request.form.get("path", "").strip()
    if path:
        sources = load_sources()
        if path not in sources["paths"]:
            sources["paths"].append(path)
            save_sources(sources)
    return redirect(url_for("sources_page"))

@app.route("/sources/remove", methods=["POST"])
def remove_source():
    path = request.form.get("path", "").strip()
    sources = load_sources()
    sources["paths"] = [p for p in sources["paths"] if p != path]
    save_sources(sources)
    return redirect(url_for("sources_page"))

@app.route("/sources/scan", methods=["POST"])
def trigger_scan():
    added = run_autodiscovery()
    return jsonify({"added": added, "count": len(added)})



@app.route("/debug/<tvdb_id>")
def debug_show(tvdb_id):
    shows = load_shows()
    show  = shows.get(tvdb_id)
    if not show:
        return f"Show {tvdb_id} not found in shows.json", 404

    media_paths = get_media_paths(show)
    report = {
        "tvdb_id":      tvdb_id,
        "name":         show.get("name"),
        "raw_stored":   show.get("media_paths", show.get("media_path", "(none)")),
        "MEDIA_ROOT":   MEDIA_ROOT,
        "resolved_paths": [],
    }
    for path in media_paths:
        exists = os.path.isdir(path)
        files_found = []
        if exists:
            for dirpath, _, filenames in os.walk(path):
                for fname in filenames:
                    if SXEX_RE.search(fname):
                        files_found.append(os.path.join(dirpath, fname))
        report["resolved_paths"].append({
            "path":   path,
            "exists": exists,
            "matched_files": files_found[:20],  # cap at 20 for readability
            "total_matched": len(files_found),
        })

    import json as _json
    return app.response_class(
        response=_json.dumps(report, indent=2),
        mimetype="application/json"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5100, debug=False)
