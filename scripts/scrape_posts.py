#!/usr/bin/env python3
"""
Blog Post Scraper

Scrapes publish dates from https://hw.glich.co/sitemap.xml
and saves them sorted from oldest to newest.

This script is designed to run in a GitHub Actions workflow.
"""

import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import sys
from pathlib import Path

# Configuration
SITEMAP_URL = "https://hw.glich.co/sitemap.xml"
OUTPUT_FILE = Path(__file__).parent.parent / "posts_dates.json"
POST_URL_PREFIX = "https://hw.glich.co/p/"
MAX_WORKERS = 3
REQUEST_DELAY = 1.0


def fetch_sitemap(url: str) -> list[str]:
    """
    Fetches the sitemap XML and extracts blog post URLs only.
    
    Args:
        url: The sitemap URL
        
    Returns:
        List of blog post URLs (starting with /p/)
    """
    print(f"Fetching sitemap from {url}...")
    
    # Add standard browser headers to avoid the 403 Forbidden blocker
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Fetch the sitemap XML with headers included
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    # Parse XML with proper namespace
    namespaces = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    root = ET.fromstring(response.content)
    
    all_urls = []
    post_urls = []
    
    # Extract URLs from sitemap
    for url_elem in root.findall('ns:url', namespaces):
        loc_elem = url_elem.find('ns:loc', namespaces)
        if loc_elem is None:
            continue
            
        loc = loc_elem.text.strip()
        all_urls.append(loc)
        
        # Only keep blog post URLs (those starting with /p/)
        if loc.startswith(POST_URL_PREFIX):
            post_urls.append(loc)
    
    print(f"Found {len(all_urls)} total URLs in sitemap")
    print(f"Filtered to {len(post_urls)} blog post URLs (prefix: {POST_URL_PREFIX})")
    return post_urls

def parse_date_string(date_str: str) -> datetime | None:
    """
    Parses various date string formats into a datetime object.
    
    Args:
        date_str: The date string to parse (e.g., "November 22, 2025")
        
    Returns:
        datetime object or None if parsing fails
    """
    date_str = date_str.strip()
    
    formats = [
        "%B %d, %Y",      # November 22, 2025
        "%b %d, %Y",      # Nov 22, 2025
        "%Y-%m-%d",       # 2025-11-22
        "%d %B %Y",       # 22 November 2025
        "%d %b %Y",       # 22 Nov 2025
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def extract_publish_date(url: str) -> dict | None:
    """
    Fetches a page and extracts the publish date from span elements.
    Retries on 429 with exponential backoff.

    Args:
        url: The page URL to scrape

    Returns:
        Dict with url and publishDate, or None if extraction fails
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for attempt in range(4):
        try:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 429:
                wait = 2 ** attempt * 5  # 5, 10, 20, 40 seconds
                print(f"  Rate limited on {url}, retrying in {wait}s...")
                time.sleep(wait)
                continue

            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Look for date in all span elements
            for span in soup.find_all("span"):
                text = span.get_text().strip()
                parsed_date = parse_date_string(text)
                if parsed_date:
                    return {
                        "url": url,
                        "publishDate": parsed_date.strftime("%Y-%m-%dT00:00:00")
                    }

            print(f"  Warning: No date found for: {url}")
            return {
                "url": url,
                "publishDate": datetime.now().strftime("%Y-%m-%dT00:00:00")
            }

        except Exception as e:
            print(f"  Error scraping {url}: {e}")
            return None

    print(f"  Giving up after retries: {url}")
    return None


def scrape_all_posts(urls: list[str], max_workers: int = 10) -> list[dict]:
    """
    Scrapes publish dates from all URLs concurrently.
    
    Args:
        urls: List of URLs to scrape
        max_workers: Maximum number of concurrent threads
        
    Returns:
        List of dicts with url and publishDate
    """
    results = []
    total = len(urls)
    completed = 0
    
    print(f"\nScraping {total} pages with {max_workers} concurrent workers...\n")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(extract_publish_date, url): url for url in urls}
        
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            completed += 1
            
            try:
                result = future.result()
                if result:
                    results.append(result)
                    print(f"  [{completed}/{total}] OK: {url[:70]}...")
                else:
                    print(f"  [{completed}/{total}] FAILED: {url[:70]}...")
            except Exception as e:
                print(f"  [{completed}/{total}] ERROR for {url}: {e}")
            
            time.sleep(REQUEST_DELAY)
    
    return results





def sort_by_date(posts: list[dict]) -> list[dict]:
    """Sorts posts by publishDate from oldest to newest."""
    return sorted(posts, key=lambda x: x["publishDate"])


def save_to_json(posts: list[dict], filename: str) -> None:
    """Saves the posts list to a JSON file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(posts)} posts to {filename}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Blog Post Scraper")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    # Step 1: Load existing posts and build a URL -> post map
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            existing_posts = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_posts = []

    existing_by_url = {p["url"]: p for p in existing_posts}
    print(f"Loaded {len(existing_by_url)} existing posts from {OUTPUT_FILE}")

    # Step 2: Fetch URLs from sitemap
    post_urls = fetch_sitemap(SITEMAP_URL)

    if not post_urls:
        print("No blog post URLs found. Exiting.")
        sys.exit(1)

    # Step 3: Skip URLs we already have a date for
    new_urls = [url for url in post_urls if url not in existing_by_url]
    print(f"Skipping {len(post_urls) - len(new_urls)} already-known URLs")
    print(f"Scraping {len(new_urls)} new URLs")

    if not new_urls:
        print("Nothing new to scrape. Exiting.")
        sys.exit(0)

    # Step 4: Scrape only the new URLs
    new_posts = scrape_all_posts(new_urls, max_workers=MAX_WORKERS)

    # Step 5: Merge new into existing and sort
    for post in new_posts:
        existing_by_url[post["url"]] = post

    sorted_posts = sort_by_date(list(existing_by_url.values()))

    # Step 6: Save to JSON
    save_to_json(sorted_posts, OUTPUT_FILE)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Blog post URLs (/p/): {len(post_urls)}")
    print(f"Already known:        {len(post_urls) - len(new_urls)}")
    print(f"Newly scraped:        {len(new_posts)}")
    print(f"Failed:               {len(new_urls) - len(new_posts)}")
    print(f"Total in file:        {len(sorted_posts)}")
    print(f"\nOldest post: {sorted_posts[0]['publishDate']} - {sorted_posts[0]['url']}")
    print(f"Newest post: {sorted_posts[-1]['publishDate']} - {sorted_posts[-1]['url']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
