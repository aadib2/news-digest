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