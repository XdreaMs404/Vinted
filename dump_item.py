import asyncio
import json
from vinted_radar.http import VintedHttpClient

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
            with open("item.json", "w", encoding="utf-8") as f:
                json.dump(items[0], f, indent=2)
            print("Wrote first item to item.json")
        else:
            print("No items found in 200 OK response.")
    else:
        print(f"Error {page.status_code}: {page.text[:200]}")

if __name__ == "__main__":
    asyncio.run(main())
