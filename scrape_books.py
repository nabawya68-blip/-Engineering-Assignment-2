"""
Scrape all books from https://books.toscrape.com/

For each book we extract:
- title
- category
- price
- in_stock (True/False, from the availability text)

If a field cannot be found we use "unknown", as required by the assignment.
The site paginates as catalogue/page-1.html, page-2.html, ... so we loop
over pages until a page returns 404 / has no books.
Category is not shown on the listing page, so we visit each book's
detail page and read it from the breadcrumb.
Output: books.csv
"""

import csv
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/"
CATALOGUE_URL = "https://books.toscrape.com/catalogue/page-{}.html"

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (assignment scraper)"})


def get_soup(url):
    response = session.get(url, timeout=30)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def get_category(book_url):
    """Read the category from the breadcrumb on the book detail page."""
    try:
        soup = get_soup(book_url)
        if soup is None:
            return "unknown"
        breadcrumb = soup.select("ul.breadcrumb li a")
        # breadcrumb: Home > Books > <Category> > <Title>
        if len(breadcrumb) >= 3:
            return breadcrumb[2].get_text(strip=True) or "unknown"
    except Exception:
        pass
    return "unknown"


def parse_listing_page(page_number):
    soup = get_soup(CATALOGUE_URL.format(page_number))
    if soup is None:
        return []
    books = []
    for article in soup.select("article.product_pod"):
        title_tag = article.select_one("h3 a")
        title = title_tag.get("title", "unknown") if title_tag else "unknown"

        price_tag = article.select_one("p.price_color")
        price_text = price_tag.get_text(strip=True) if price_tag else "unknown"
        price_match = re.search(r"[\d.]+", price_text)
        price = float(price_match.group()) if price_match else "unknown"

        availability_tag = article.select_one("p.availability")
        availability = (
            availability_tag.get_text(strip=True).lower() if availability_tag else ""
        )
        if "in stock" in availability:
            in_stock = True
        elif "out of stock" in availability:
            in_stock = False
        else:
            in_stock = "unknown"

        book_url = urljoin(BASE_URL + "catalogue/", title_tag.get("href")) if title_tag else None
        books.append(
            {
                "title": title,
                "price": price,
                "in_stock": in_stock,
                "book_url": book_url,
            }
        )
    return books


def main():
    all_books = []
    page = 1
    while True:
        books = parse_listing_page(page)
        if not books:
            print(f"Page {page}: no books, stopping.")
            break
        print(f"Page {page}: {len(books)} books")
        all_books.extend(books)
        page += 1

    print(f"\nTotal books found: {len(all_books)}")
    print("Fetching category for each book from its detail page...")

    with ThreadPoolExecutor(max_workers=10) as executor:
        categories = list(
            executor.map(
                lambda b: get_category(b["book_url"]) if b["book_url"] else "unknown",
                all_books,
            )
        )

    for book, category in zip(all_books, categories):
        book["category"] = category
        del book["book_url"]

    # Order columns as required: category, title/name, price, in_stock
    rows = [
        {
            "category": b["category"],
            "title": b["title"],
            "price": b["price"],
            "in_stock": b["in_stock"],
        }
        for b in all_books
    ]

    output_file = "books.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "title", "price", "in_stock"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} rows to {output_file}")


if __name__ == "__main__":
    main()
