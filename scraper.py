import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import sys
import io

import argparse

from pdfminer.high_level import extract_text
from playwright.async_api import async_playwright

visited = set()
emails_found = set()
queue = asyncio.Queue()
js_render_count = 0

MAX_PAGES = 120
CONCURRENT_WORKERS = 20
processed_count = 0
MAX_DEPTH = 3
JS_RENDER_LIMIT = 5
REQUEST_DELAY = (0.3, 1.2)

# professional CLI defaults (can be overridden)
email_regex = re.compile(
    r"[a-zA-Z0-9._%+-]+\s*(?:@|\[at\]|\(at\)|at)\s*[a-zA-Z0-9.-]+\s*(?:\.|\[dot\]|\(dot\)|dot)\s*(com|edu|org|net|gov|in|co|io|info)",
    re.IGNORECASE
)


def get_domain(url):
    return urlparse(url).netloc


def extract_emails(text):
    raw = re.finditer(email_regex, text)

    for m in raw:
        e = m.group().lower()

        e = e.replace(" at ", "@").replace("[at]", "@").replace("(at)", "@")
        e = e.replace(" dot ", ".").replace("[dot]", ".").replace("(dot)", ".")
        e = re.sub(r"\s+", "", e)

        # strict validation
        if e.count("@") != 1:
            continue

        local, domain = e.split("@")

        if "." not in domain:
            continue

        if "/" in e or ":" in e:
            continue

        if e.endswith(".png") or e.endswith(".jpg"):
            continue

        if e not in emails_found:
            emails_found.add(e)
            print("EMAIL:", e)


async def extract_pdf(session, url):
    try:
        async with session.get(url, timeout=10) as r:
            data = await r.read()
            text = extract_text(io.BytesIO(data))
            extract_emails(text)
    except:
        pass


async def fetch_js(url):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=15000)
            content = await page.content()
            extract_emails(content)
            await browser.close()
    except:
        pass


async def fetch(session, url, domain, depth=0):
    global processed_count
    global js_render_count

    if url in visited:
        return

    if get_domain(url) != domain:
        return

    if processed_count >= MAX_PAGES:
        return

    if depth > MAX_DEPTH:
        return

    import random
    await asyncio.sleep(random.uniform(*REQUEST_DELAY))

    visited.add(url)
    processed_count += 1

    print("Visiting:", url)

    # PDF detection
    if url.lower().endswith(".pdf"):
        await extract_pdf(session, url)
        return

    try:
        async with session.get(url, timeout=8) as response:
            html = await response.text()
    except:
        return

    extract_emails(html)

    soup = BeautifulSoup(html, "html.parser")

    # limited JS rendering for stealth
    if "@" not in html and js_render_count < JS_RENDER_LIMIT:
        js_render_count += 1
        await fetch_js(url)

    from urllib.parse import urldefrag
    for a in soup.find_all("a", href=True):
        link = urljoin(url, a["href"])
        link, _ = urldefrag(link)

        # strip pagination stealth
        if "?page=" in link or "&page=" in link:
            continue

        if link not in visited:
            await queue.put((link, depth + 1))


async def worker(session, domain):
    while True:
        url, depth = await queue.get()
        await fetch(session, url, domain, depth)
        queue.task_done()


async def main_async(start_url):
    domain = get_domain(start_url)

    await queue.put((start_url, 0))

    async with aiohttp.ClientSession() as session:
        tasks = []
        for _ in range(CONCURRENT_WORKERS):
            tasks.append(asyncio.create_task(worker(session, domain)))

        await queue.join()

        for t in tasks:
            t.cancel()

    filename = f"{domain}-email-addresses.txt"
    with open(filename, "w") as f:
        for email in sorted(emails_found):
            f.write(email + "\n")

    print(f"\nSaved {len(emails_found)} emails to {filename}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Async Recon Email Scraper",
        epilog="Example: python scraper.py https://target.com --max-pages 200 --depth 4 --workers 30"
    )

    parser.add_argument("url", help="Target start URL")
    parser.add_argument("--max-pages", type=int, default=120, help="Maximum pages to crawl")
    parser.add_argument("--depth", type=int, default=3, help="Maximum crawl depth")
    parser.add_argument("--workers", type=int, default=20, help="Concurrent async workers")
    parser.add_argument("--js-limit", type=int, default=5, help="Maximum JS render attempts")

    args = parser.parse_args()

    # apply runtime tuning
    MAX_PAGES = args.max_pages
    MAX_DEPTH = args.depth
    CONCURRENT_WORKERS = args.workers
    JS_RENDER_LIMIT = args.js_limit

    print("\n[ Recon Email Scraper ]")
    print("Target:", args.url)
    print("Max Pages:", MAX_PAGES)
    print("Depth:", MAX_DEPTH)
    print("Workers:", CONCURRENT_WORKERS)
    print("JS Render Limit:", JS_RENDER_LIMIT)
    print("\nStarting crawl...\n")

    asyncio.run(main_async(args.url))
    