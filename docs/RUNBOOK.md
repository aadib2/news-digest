# Runbook

## Feedback Database (SQLite)

The bot uses a SQLite database (`feedback.db`) for persistent feedback storage.

### Configuration
- **Environment variable**: `DATABASE_PATH` (default: `./data/feedback.db`)
  - Legacy `FEEDBACK_DB_PATH` also supported for backward compatibility
- **Schema**: Auto-created on first run. Tables:
  - `articles` — one row per digest message (maps `message_id` → article metadata)
  - `reactions` — one row per 👍/👎/🔖 reaction
- **Pragmas**: WAL mode + 5s busy timeout for concurrency safety

### Migration from old `feedback.json`
- On first run with the new code, the database is created fresh (empty)
- Old `feedback.json` is **not** auto-migrated — if you need historical data, run a one-off script (see below)
- The JSON file can be deleted after confirming the new DB works

### Manual migration (optional)
If you want to import old `feedback.json` data:
```python
# Run once locally or in a DigitalOcean/Railway shell
import json, sqlite3, os
db = sqlite3.connect(os.getenv("DATABASE_PATH", "./data/feedback.db"))
with open("feedback.json") as f:
    fb = json.load(f)

# articles from message_article_map
for msg_id, art in fb.get("message_article_map", {}).items():
    db.execute("""INSERT OR IGNORE INTO articles (message_id, title, url, source, category, relevance_score)
                  VALUES (?, ?, ?, ?, ?, ?)""",
               (msg_id, art["title"], art["url"], art["source"], art.get("category", ""), art.get("relevance_score", 0)))

# reactions from upvoted/downvoted/saved
for table, emoji in [("upvoted", "👍"), ("downvoted", "👎"), ("saved", "🔖")]:
    for entry in fb.get(table, []):
        db.execute("""INSERT INTO reactions (message_id, emoji, reacted_at)
                      VALUES (?, ?, ?)""",
                   (entry["message_id"], emoji, entry["timestamp"]))

db.commit()
```

### DigitalOcean Droplet deployment checklist
1. Ensure `DATABASE_PATH=/data/feedback.db` in environment (or your chosen path)
2. Create the data directory: `mkdir -p /data` (or wherever your DB path points)
3. Ensure the bot user has write permissions to the directory
4. No separate volume needed — the filesystem persists on the droplet

### Railway deployment checklist
1. Volume mounted at `/data` (Project → Service → Volumes → Add Volume → Mount Path: `/data`)
2. `DATABASE_PATH=/data/feedback.db` set in Railway Variables
3. No `FEEDBACK_PATH` variable (old JSON config removed)

### Local development
- Uses `./data/feedback.db` in the project root (fallback when `DATABASE_PATH` not set)
- Delete `data/feedback.db` to reset local feedback state

### Troubleshooting
- **"no such table" errors**: Delete the DB file and let it re-create (data loss!)
- **Permission denied on path**: Directory doesn't exist or wrong permissions
- **DB locked**: Multiple bot instances; use `sqlite3 -cmd ".timeout 5000"` or ensure single instance

---

## Notion Reading-List Integration

The 🔖 **Save to Notion** button on each digest article creates a page in a Notion database.

### Configuration
- **Environment variables** (both required; the feature self-disables without them):
  - `NOTION_TOKEN` — internal integration secret from https://www.notion.so/my-integrations
  - `NOTION_DATABASE_ID` — 32-char hex from the database URL
- The integration must be explicitly **connected** to the database (Notion **⋯** → Connections), otherwise the API returns 404 even with a valid token.
- API version is pinned in code: `NOTION_VERSION = "2022-06-28"` (`agent/notion_client.py`).

### Inspect the database schema (source of truth)
```bash
uv run python -m test.test_notion_connection
```
Prints every property name, type, and select/status option. Current schema:

| Property | Type | Written by bot |
|----------|------|----------------|
| `Title` | title | yes |
| `Article Link` | url | yes (also the dedup key) |
| `Source` | select | yes |
| `Category` | select | yes (mapped) |
| `Technical Summary` | rich_text | yes (parsed from Claude summary) |
| `Why It Matters` | rich_text | yes (parsed from Claude summary) |
| `Date Added` | date | yes (UTC now) |
| `Status` | select | yes (`To Read`) |
| `Key Takeaways` | rich_text | no — you fill in |
| `Subcategories` | multi_select | no — you fill in |
| `Date Read` | date | no — you fill in |

### Where the mappings live
All in `agent/notion_client.py`:
- `CATEGORY_TO_NOTION` — bot category → `Category` option (`machine_learning / AI` → `ML/AI`, etc.)
- `STATUS_KEY` / `STATUS_DEFAULT` — `"select"` / `"To Read"` (must match the property's actual *type*; a `status`-type property needs `"status"` instead)
- `build_properties()` — the full payload; property names here must match the schema exactly (case- and space-sensitive)

### Dedup
Before creating a page, `url_exists()` queries the database filtered on `Article Link == url`. Archived pages don't match, so re-saving an archived article recreates it. The button is also edited to a disabled **Saved ✓** state, which persists in Discord's message JSON across bot restarts.

### Rotating the token
1. Notion → integration → **Rotate secret**
2. Update `NOTION_TOKEN` in `.env` (local) and the droplet's environment
3. Restart the bot — the token is read per request via `config()`, but the process must pick up the new env

### Gotchas
- **Property *type* mismatch** → `400 validation_error: "Source is expected to be select"`. Align `build_properties()` with the inspection output.
- **Property *name* mismatch** → `400 "Could not find property with name or id: X"`. Fix it in `build_properties()` **and** the `url_exists()` filter.
- **Unknown select option names are auto-created**, so they fail silently rather than erroring. `SOURCE_TO_NOTION` maps the bot's source names to your `Source` options (`HackerNews` → `Hacker News`, `Towards Data Science` → `TDS`); unmapped sources are omitted rather than creating junk options. Add an entry when you add a fetcher.
- **Tests are hermetic**: `test/test_notion_client.py` hard-sets test credentials, so exported shell vars can't leak in. The real-Notion round-trip is opt-in: `uv run python -m test.test_notion_client --live` (loads `.env` with override; creates then archives a test page).