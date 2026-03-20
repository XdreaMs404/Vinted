import asyncio
from curl_cffi import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_vinted_session():
    url = "https://www.vinted.fr/"
    impersonate = "chrome120"  # Test newer version
    
    logger.info(f"Testing Vinted homepage with impersonate={impersonate}")
    
    async with requests.AsyncSession(impersonate=impersonate) as s:
        resp = await s.get(url, timeout=30)
        
        logger.info(f"Status Code: {resp.status_code}")
        logger.info(f"Response Headers: {dict(resp.headers)}")
        logger.info(f"Cookies in session: {dict(s.cookies)}")
        
        if "_vinted_fr_session" in s.cookies:
            logger.info("SUCCESS: _vinted_fr_session found!")
        else:
            logger.warning("FAILURE: _vinted_fr_session NOT found.")
            
        # Try a second request to see if it's set later
        await asyncio.sleep(2)
        logger.info("Attempting second request...")
        resp2 = await s.get(url, timeout=30)
        logger.info(f"Second Status Code: {resp2.status_code}")
        logger.info(f"Cookies after second request: {dict(s.cookies)}")

if __name__ == "__main__":
    asyncio.run(debug_vinted_session())
