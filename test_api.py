import asyncio
from curl_cffi import requests

async def main():
    s = requests.AsyncSession(impersonate="chrome120")
    print("Fetching homepage for cookie...")
    resp = await s.get("https://www.vinted.fr/")
    print(f"Homepage status: {resp.status_code}")
    print(f"Cookies: {dict(s.cookies)}")

    print("\nFetching API catalog page...")
    url = "https://www.vinted.fr/api/v2/catalog/items?catalog_ids=1439&page=1&per_page=96"
    resp2 = await s.get(url)
    
    print(f"API status: {resp2.status_code}")
    print(f"API body: {resp2.text[:200]}")
    await s.close()

if __name__ == "__main__":
    asyncio.run(main())
