"""
spider.py — Scrapling Spider for Review Mining

Target: quotes.toscrape.com (legal scraping sandbox)
Structure mirrors real e-commerce reviews:
  - text     → review body
  - author   → reviewer name
  - tags     → product category labels

Scrapes all 10 pages concurrently.
"""

import os
# Fix for Windows SSL certificate issue with curl-cffi backend
os.environ["CURL_CA_BUNDLE"] = ""

from scrapling.spiders import Spider, Response


class ReviewSpider(Spider):
    name = "ecom_reviews"

    # Scrape all 10 pages upfront — avoids needing next-page link following
    start_urls = [
        f"https://quotes.toscrape.com/page/{i}/"
        for i in range(1, 11)
    ]

    fetcher_options = {
        "disable_verify_ssl": True,   # Windows SSL fix
    }

    # Polite crawl settings
    concurrent_requests = 3
    download_delay = 0.3

    async def parse(self, response: Response):
        """
        Extract each quote block as a 'review':
          - text       → the review content
          - author     → who wrote it
          - tags       → product category (e.g. 'humor', 'inspirational')
          - source_url → which page it came from
        """
        reviews = response.css("div.quote")

        if not reviews:
            self.logger.warning(f"No reviews found on {response.url}")
            return

        for review in reviews:
            # Strip decorative quote characters from text
            raw_text = review.css("span.text::text").get("").strip()
            clean_text = raw_text.strip("\u201c\u201d\"'")

            author = review.css("small.author::text").get("").strip()
            tags = review.css("a.tag::text").getall()

            yield {
                "text": clean_text,
                "author": author,
                "tags": tags if tags else ["uncategorized"],
                "source_url": str(response.url),
            }
