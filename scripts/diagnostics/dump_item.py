import asyncio
import json
from pathlib import Path

from vinted_radar.http import VintedHttpClient

OUTPUT_PATH = Path(__file__).resolve().parent / "output" / "item.json"


async def main():
    client = VintedHttpClient(impersonate="chrome120")
    print("Warming up to get cookies...")
    await client.warm_up_async()
    
    url = "https://www.vinted.fr/api/v2/catalog/items?catalog_ids=1439&page=1&per_page=96"
    print(f"Fetching {url}...")
    page = await client.get_text_async(url)
    
    if page.status_code == 200:
        data = json.loads(page.text)
        items = data.get("items", [])
        if items:
            OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            with OUTPUT_PATH.open("w", encoding="utf-8") as f:
                json.dump(items[0], f, indent=2)
            print(f"Wrote first item to {OUTPUT_PATH}")
        else:
            print("No items found in 200 OK response.")
    else:
        print(f"Error {page.status_code}: {page.text[:200]}")

if __name__ == "__main__":
    asyncio.run(main())
