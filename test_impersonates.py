import asyncio
from curl_cffi import requests
from curl_cffi.requests import BrowserType

async def test_impersonate(browser):
    url = "https://www.vinted.fr/catalog?search_text=&catalog[]=1439&page=1&per_page=96"
    print(f"\n--- Testing {browser} ---")
    try:
        async with requests.AsyncSession(impersonate=browser) as s:
            r = await s.get(url, timeout=10)
            print(f"Status: {r.status_code}")
            if "datadome" in r.text.lower() or r.status_code == 403:
                print("DataDome block detected.")
            else:
                print("SUCCESSFUL fetch.")
    except Exception as e:
        print(f"Error: {e}")

async def main():
    browsers = ["chrome116", "chrome120", "chrome110", "edge101", "safari15_5"]
    for b in browsers:
        await test_impersonate(b)

if __name__ == "__main__":
    asyncio.run(main())
