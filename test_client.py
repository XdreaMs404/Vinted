import asyncio
from vinted_radar.http import VintedHttpClient

async def main():
    client = VintedHttpClient(impersonate="chrome120", request_delay=1.0)
    print("Testing warm_up...")
    await client.warm_up_async()
    print("Warm-up complete.")
    
    url = "https://www.vinted.fr/catalog?search_text=&catalog[]=1439&page=1&per_page=96"
    print(f"Requesting {url}")
    page = await client.get_text_async(url)
    
    print(f"Status: {page.status_code}")
    if page.status_code == 403:
        print("DataDome blocked the catalog request despite warmup.")
    else:
        print(f"Success! Body length: {len(page.text)}")

if __name__ == "__main__":
    asyncio.run(main())
