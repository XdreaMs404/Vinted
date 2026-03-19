import argparse
import asyncio
import platform
import re
import sys
import time as time_module
import random
import socket
import threading
import urllib.request
from time import time
from colorama import Fore, Style, init
import httpx
from bs4 import BeautifulSoup
import os
import requests
import webbrowser
import socks  # Added missing import

# Initialize colorama
init(autoreset=True)

# Constants
MAX_THREADS = 100  # Number of threads for checking proxies
TIMEOUT = 5  # Timeout for proxy checks
TEST_URL = "http://ip-api.com/json"  # URL to test proxies against
OUTPUT_FILE = "working_proxies.txt"

user_agents = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.94 Chrome/37.0.2062.94 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.85 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/600.8.9 (KHTML, like Gecko) Version/8.0.8 Safari/600.8.9",
    "Mozilla/5.0 (iPad; CPU OS 8_4_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12H321 Safari/600.1.4",
    "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.85 Safari/537.36",
]

try:
    with open("user_agents.txt", "r") as f:
        for line in f:
            user_agents.append(line.replace("\n", ""))
except FileNotFoundError:
    pass

class Scraper:
    def __init__(self, method, _url):
        self.method = method
        self._url = _url

    def get_url(self, **kwargs):
        return self._url.format(**kwargs, method=self.method)

    async def get_response(self, client):
        return await client.get(self.get_url())

    async def handle(self, response):
        return response.text

    async def scrape(self, client):
        response = await self.get_response(client)
        proxies = await self.handle(response)
        pattern = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}(?::\d{1,5})?")
        return re.findall(pattern, proxies)

# From spys.me
class SpysMeScraper(Scraper):
    def __init__(self, method):
        super().__init__(method, "https://spys.me/{mode}.txt")

    def get_url(self, **kwargs):
        mode = "proxy" if self.method == "http" else "socks" if self.method == "socks" else "unknown"
        if mode == "unknown":
            raise NotImplementedError
        return super().get_url(mode=mode, **kwargs)

# From proxyscrape.com
class ProxyScrapeScraper(Scraper):
    def __init__(self, method, timeout=1000, country="All"):
        self.timout = timeout
        self.country = country
        super().__init__(method,
                         "https://api.proxyscrape.com/?request=getproxies"
                         "&proxytype={method}"
                         "&timeout={timout}"
                         "&country={country}")

    def get_url(self, **kwargs):
        return super().get_url(timout=self.timout, country=self.country, **kwargs)

# From geonode.com - A little dirty, grab http(s) and socks but use just for socks
class GeoNodeScraper(Scraper):
    def __init__(self, method, limit="500", page="1", sort_by="lastChecked", sort_type="desc"):
        self.limit = limit
        self.page = page
        self.sort_by = sort_by
        self.sort_type = sort_type
        super().__init__(method,
                         "https://proxylist.geonode.com/api/proxy-list?"
                         "&limit={limit}"
                         "&page={page}"
                         "&sort_by={sort_by}"
                         "&sort_type={sort_type}")

    def get_url(self, **kwargs):
        return super().get_url(limit=self.limit, page=self.page, sort_by=self.sort_by, sort_type=self.sort_type, **kwargs)

# From proxy-list.download
class ProxyListDownloadScraper(Scraper):
    def __init__(self, method, anon):
        self.anon = anon
        super().__init__(method, "https://www.proxy-list.download/api/v1/get?type={method}&anon={anon}")

    def get_url(self, **kwargs):
        return super().get_url(anon=self.anon, **kwargs)

# For websites using table in html
class GeneralTableScraper(Scraper):
    async def handle(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        proxies = set()
        table = soup.find("table", attrs={"class": "table table-striped table-bordered"})
        for row in table.find_all("tr"):
            count = 0
            proxy = ""
            for cell in row.find_all("td"):
                if count == 1:
                    proxy += ":" + cell.text.replace("&nbsp;", "")
                    proxies.add(proxy)
                    break
                proxy += cell.text.replace("&nbsp;", "")
                count += 1
        return "\n".join(proxies)

# For websites using div in html
class GeneralDivScraper(Scraper):
    async def handle(self, response):
        soup = BeautifulSoup(response.text, "html.parser")
        proxies = set()
        table = soup.find("div", attrs={"class": "list"})
        for row in table.find_all("div"):
            count = 0
            proxy = ""
            for cell in row.find_all("div", attrs={"class": "td"}):
                if count == 2:
                    break
                proxy += cell.text+":"
                count += 1
            proxy = proxy.rstrip(":")
            proxies.add(proxy)
        return "\n".join(proxies)

# For scraping live proxylist from github
class GitHubScraper(Scraper):
    async def handle(self, response):
        tempproxies = response.text.split("\n")
        proxies = set()
        for prxy in tempproxies:
            if self.method in prxy:
                proxies.add(prxy.split("//")[-1])
        return "\n".join(proxies)

scrapers = [
    SpysMeScraper("http"),
    SpysMeScraper("socks"),
    ProxyScrapeScraper("http"),
    ProxyScrapeScraper("socks4"),
    ProxyScrapeScraper("socks5"),
    GeoNodeScraper("socks"),
    ProxyListDownloadScraper("https", "elite"),
    ProxyListDownloadScraper("http", "elite"),
    ProxyListDownloadScraper("http", "transparent"),
    ProxyListDownloadScraper("http", "anonymous"),
    GeneralTableScraper("https", "http://sslproxies.org"),
    GeneralTableScraper("http", "http://free-proxy-list.net"),
    GeneralTableScraper("http", "http://us-proxy.org"),
    GeneralTableScraper("socks", "http://socks-proxy.net"),
    GeneralDivScraper("http", "https://freeproxy.lunaproxy.com/"),
    GitHubScraper("http", "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt"),
    GitHubScraper("socks4", "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt"),
    GitHubScraper("socks5", "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt"),
    GitHubScraper("http", "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt"),
    GitHubScraper("socks", "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt"),
    GitHubScraper("https", "https://raw.githubusercontent.com/zloi-user/hideip.me/main/https.txt"),
    GitHubScraper("http", "https://raw.githubusercontent.com/zloi-user/hideip.me/main/http.txt"),
    GitHubScraper("socks4", "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks4.txt"),
    GitHubScraper("socks5", "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks5.txt"),
]

def verbose_print(verbose, message):
    if verbose:
        print(message)

async def scrape_proxies(method, output, verbose):
    now = time_module.time()
    methods = [method]
    if method == "socks":
        methods += ["socks4", "socks5"]
    proxy_scrapers = [s for s in scrapers if s.method in methods]
    if not proxy_scrapers:
        raise ValueError("Method not supported")
    verbose_print(verbose, "Scraping proxies...")
    proxies = []

    tasks = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        async def scrape_scraper(scraper):
            try:
                verbose_print(verbose, f"Looking {scraper.get_url()}...")
                proxies.extend(await scraper.scrape(client))
            except Exception:
                pass

        for scraper in proxy_scrapers:
            tasks.append(asyncio.ensure_future(scrape_scraper(scraper)))

        await asyncio.gather(*tasks)

    proxies = set(proxies)
    verbose_print(verbose, f"Writing {len(proxies)} proxies to file...")
    with open(output, "w") as f:
        f.write("\n".join(proxies))
    verbose_print(verbose, "Done!")
    verbose_print(verbose, f"Took {time_module.time() - now} seconds")

class Proxy:
    def __init__(self, method, proxy):
        if method.lower() not in ["http", "https", "socks4", "socks5"]:
            raise NotImplementedError("Only HTTP, HTTPS, SOCKS4, and SOCKS5 are supported")
        self.method = method.lower()
        self.proxy = proxy

    def is_valid(self):
        return re.match(r"\d{1,3}(?:\.\d{1,3}){3}(?::\d{1,5})?$", self.proxy)

    def check(self, site, timeout, user_agent, verbose):
        if self.method in ["socks4", "socks5"]:
            socks.set_default_proxy(socks.SOCKS4 if self.method == "socks4" else socks.SOCKS5,
                                  self.proxy.split(':')[0], int(self.proxy.split(':')[1]))
            socket.socket = socks.socksocket
            try:
                start_time = time()
                urllib.request.urlopen(site, timeout=timeout)
                end_time = time()
                time_taken = end_time - start_time

                # Get proxy details
                proxy_ip = self.proxy.split(':')[0]
                try:
                    ip_info = requests.get(f"http://ip-api.com/json/{proxy_ip}", timeout=5).json()
                    country = ip_info.get('country', 'Unknown')
                except Exception:
                    country = 'Unknown'

                print(f"{Fore.GREEN}Live: {self.proxy} | Country: {country} | IP: {proxy_ip} | Ping: {int(time_taken*1000)}ms{Style.RESET_ALL}")

                # Save working proxy immediately
                with open(OUTPUT_FILE, "a") as f:
                    f.write(f"{self.proxy}\n")

                return True, time_taken, None
            except Exception as e:
                print(f"{Fore.RED}Dead: {self.proxy} | Error: {str(e)}{Style.RESET_ALL}")
                return False, 0, e
        else:
            url = self.method + "://" + self.proxy
            proxy_support = urllib.request.ProxyHandler({self.method: url})
            opener = urllib.request.build_opener(proxy_support)
            urllib.request.install_opener(opener)
            req = urllib.request.Request(self.method + "://" + site)
            req.add_header("User-Agent", user_agent)
            try:
                start_time = time()
                urllib.request.urlopen(req, timeout=timeout)
                end_time = time()
                time_taken = end_time - start_time

                # Get proxy details
                proxy_ip = self.proxy.split(':')[0]
                try:
                    ip_info = requests.get(f"http://ip-api.com/json/{proxy_ip}", timeout=5).json()
                    country = ip_info.get('country', 'Unknown')
                except Exception:
                    country = 'Unknown'

                print(f"{Fore.GREEN}Live: {self.proxy} | Country: {country} | IP: {proxy_ip} | Ping: {int(time_taken*1000)}ms{Style.RESET_ALL}")

                # Save working proxy immediately
                with open(OUTPUT_FILE, "a") as f:
                    f.write(f"{self.proxy}\n")

                return True, time_taken, None
            except Exception as e:
                print(f"{Fore.RED}Dead: {self.proxy} | Error: {str(e)}{Style.RESET_ALL}")
                return False, 0, e

    def __str__(self):
        return self.proxy

def check_proxies(file, timeout, method, site, verbose, random_user_agent):
    proxies = []
    with open(file, "r") as f:
        for line in f:
            proxies.append(Proxy(method, line.replace("\n", "")))

    print(f"Checking {len(proxies)} proxies")
    proxies = list(filter(lambda x: x.is_valid(), proxies))
    valid_proxies = []
    user_agent = random.choice(user_agents)

    def check_proxy(proxy, user_agent):
        new_user_agent = user_agent
        if random_user_agent:
            new_user_agent = random.choice(user_agents)
        valid, time_taken, error = proxy.check(site, timeout, new_user_agent, verbose)
        if valid:
            valid_proxies.append(proxy)

    threads = []
    for proxy in proxies:
        t = threading.Thread(target=check_proxy, args=(proxy, user_agent))
        threads.append(t)
        t.start()
        time_module.sleep(0.1)  # Small delay between starting threads

    for t in threads:
        t.join()

    print(f"\nFound {len(valid_proxies)} valid proxies")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        help="Dismiss the proxy after -t seconds",
        default=5,
    )
    parser.add_argument("-p", "--proxy", help="Check HTTPS, HTTP, SOCKS4, or SOCKS5 proxies", default="http")
    parser.add_argument("-l", "--list", help="Path to your proxy list file", default="output.txt")
    parser.add_argument(
        "-s",
        "--site",
        help="Check with specific website like google.com",
        default="https://google.com/",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Increase output verbosity",
        action="store_true",
    )
    parser.add_argument(
        "-r",
        "--random_agent",
        help="Use a random user agent per proxy",
        action="store_true",
    )
    args = parser.parse_args()

    # Clear screen
    os.system('cls' if os.name == 'nt' else 'clear')

    # Print banner
    print("""
██╗░░██╗░█████╗░██╗░░░░░██████╗░███████╗███╗░░██╗
██║░░██║██╔══██╗██║░░░░░██╔══██╗██╔════╝████╗░██║
███████║██║░░██║██║░░░░░██║░░██║█████╗░░██╔██╗██║
██╔══██║██║░░██║██║░░░░░██║░░██║██╔══╝░░██║╚████║
██║░░██║╚█████╔╝███████╗██████╔╝███████╗██║░╚███║
╚═╝░░╚═╝░╚════╝░╚══════╝╚═════╝░╚══════╝╚═╝░░╚══╝ Dread: /u/Holden""")

    # Create/clear output file
    open(OUTPUT_FILE, 'w').close()

    print(f"{Fore.YELLOW}[INFO] Starting proxy scraping and checking{Style.RESET_ALL}\n")

    start_time = time_module.time()

    while True:
        # Scrape proxies
        if sys.version_info >= (3, 7):
            asyncio.run(scrape_proxies(args.proxy, args.list, args.verbose))
        else:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(scrape_proxies(args.proxy, args.list, args.verbose))
            loop.close()

        # Check proxies
        check_proxies(file=args.list, timeout=args.timeout, method=args.proxy, site=args.site, verbose=args.verbose,
                     random_user_agent=args.random_agent)

        # Short sleep to avoid overwhelming the system
        time_module.sleep(1)

if __name__ == "__main__":
    main()