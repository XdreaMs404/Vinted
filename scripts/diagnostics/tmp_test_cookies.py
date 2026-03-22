import asyncio
from curl_cffi import requests

async def main():
    async with requests.AsyncSession(impersonate="chrome116") as s:
        await s.get("https://httpbin.org/cookies/set?foo=bar")
        print("Cookies type:", type(s.cookies))
        print("Cookies list:", list(s.cookies))
        for c in s.cookies:
            print("Iterated:", type(c), c)
        print("get() method:", s.cookies.get("foo"))

if __name__ == "__main__":
    asyncio.run(main())
