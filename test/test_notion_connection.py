import asyncio, os
from dotenv import load_dotenv
import aiohttp

load_dotenv()
TOKEN = os.environ["NOTION_TOKEN"]
DB_ID = os.environ["NOTION_DATABASE_ID"]

async def main():
    async with aiohttp.ClientSession() as s:
        async with s.get(
            f"https://api.notion.com/v1/databases/{DB_ID}",
            headers={"Authorization": f"Bearer {TOKEN}", "Notion-Version": "2022-06-28"},
        ) as r:
            data = await r.json()
            if r.status != 200:
                print("ERROR", r.status, data)
                return
            for name, prop in data.get("properties", {}).items():
                line = f"{name!r}: {prop['type']}"
                for key in ("select", "status", "multi_select"):
                    if prop["type"] == key:
                        line += " options=" + str([o["name"] for o in prop[key]["options"]])
                print(line)

asyncio.run(main())