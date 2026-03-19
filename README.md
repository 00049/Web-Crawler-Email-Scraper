# Email Scraper

An async Python web crawler that discovers and extracts email addresses 
from websites. Supports static HTML, JavaScript-rendered pages (via Playwright), 
and PDF files.

## Features
- Async crawling with configurable concurrency (aiohttp)
- JS rendering fallback via headless Chromium (Playwright)
- PDF text extraction (pdfminer)
- Obfuscated email detection (e.g. user [at] domain [dot] com)
- Configurable depth, page limit, and worker count
- Polite crawling with randomized request delays

## Usage
pip install aiohttp beautifulsoup4 pdfminer.six playwright
playwright install chromium

python scraper.py https://example.com --max-pages 200 --depth 4 --workers 30

## Options
--max-pages   Max pages to crawl (default: 120)
--depth       Max crawl depth (default: 3)
--workers     Concurrent async workers (default: 20)
--js-limit    Max JS render attempts (default: 5)

## Output
Emails saved to <domain>-email-addresses.txt
