from urllib.parse import urljoin
import logging
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from src.config import DEFAULT_TIMEOUT_MS, FLIPKART_BASE_URL
from src.schemas import ProductCandidate

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from src.scrapers.utils import (
    build_search_query,
    clean_price_to_inr,
    open_context,
    polite_delay,
    text_or_empty,
)


def _flipkart_listing_links(page, max_results: int) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    # Try multiple known Flipkart search-result card selectors
    card_selectors = [
        "div[data-id] a[href*='/p/']",   # newer layout
        "a.CGtC98",                       # product card anchor
        "a._1fQZEK",                      # older layout
        "a.s1Q9rs",                       # another variant
        "a[href*='/p/']",                 # broadest fallback
    ]
 
    anchors = []
    for sel in card_selectors:
        anchors = page.query_selector_all(sel)
        if anchors:
            break

    for anchor in anchors:
        href = (anchor.get_attribute("href") or "").strip()
        if not href or "/p/" not in href:
            continue

        url = urljoin(FLIPKART_BASE_URL, href.split("?")[0])
        if url in seen:
            continue

        seen.add(url)
        # Get title from sibling/child or attribute fallback
        title = (
            anchor.get_attribute("title")
            or anchor.get_attribute("aria-label")
            or ""
        ).strip()
        if not title:
            # Try child elements
            name_node = anchor.query_selector("div.KzDlHZ, div._4rR01T, div.WKTcLC")
            title = (name_node.inner_text() if name_node else "").strip()
        if not title:
            title = (anchor.inner_text() or "")[:220].strip()

        items.append({"title": title, "url": url})
        if len(items) >= max_results:
            break

    return items


def _try_text(page, selectors: list[str]) -> str:
    """Try multiple CSS selectors and return first non-empty result."""
    for sel in selectors:
        val = text_or_empty(page, sel)
        if val:
            return val
    return ""


def _extract_from_ld_json(soup: BeautifulSoup) -> tuple[str, str]:
    title = ""
    price = ""

    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        if '"@type":"Product"' not in raw and '"@type": "Product"' not in raw:
            continue

        if '"name"' in raw and not title:
            import json
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    title = str(data.get("name") or "")
                    offers = data.get("offers") or {}
                    if isinstance(offers, dict):
                        price = str(offers.get("price") or "")
            except Exception:
                continue

    if price and not price.startswith("₹"):
        price = f"₹{price}"

    return title.strip(), price.strip()


def _flipkart_extract_page_data(page, fallback: str) -> tuple[str, str]:
    html = page.content()
    soup = BeautifulSoup(html, "lxml")

    ld_title, ld_price = _extract_from_ld_json(soup)

    # Many websites include Open Graph metadata
    meta_title = (
        (soup.select_one("meta[property='og:title']") or {}).get("content", "")
        if soup.select_one("meta[property='og:title']")
        else ""
    )
    meta_price = (
        (soup.select_one("meta[property='product:price:amount']") or {}).get("content", "")
        if soup.select_one("meta[property='product:price:amount']")
        else ""
    )

    title = (
        _try_text(page, [
            "span.VU-ZEz",
            "h1.yhB1nd",
            "span.B_NuCI",
            "h1",
        ])
        or ld_title
        or meta_title
        or fallback
    )

    price_text = (
        _try_text(page, [
            "div.Nx9bqj.CxhGGd",
            "div.Nx9bqj",
            "div._30jeq3._16Jk6d",
            "div._30jeq3",
            "div._25b18",
            "div.CEmiEU span",
        ])
        or (f"₹{meta_price}" if meta_price else "")
        or ld_price
    )

    return title.strip(), price_text.strip()


def _flipkart_extract_name(page, fallback: str) -> str:
    title, _price_text = _flipkart_extract_page_data(page, fallback)
    return title


def _flipkart_extract_price(page) -> str:
    _title, price_text = _flipkart_extract_page_data(page, "")
    return price_text


def _flipkart_extract_specs(page) -> tuple[str, dict[str, str]]:
    specs: dict[str, str] = {}

    # Try multiple known spec-table row selectors in order
    row_selectors = [
        "div._14cfVK tr",      # 2024 spec table wrapper
        "div.GNOMPZ tr",
        "div._2TID2M tr",
        "div.hGSR34 tr",
        "table tr",            # generic fallback
    ]
    rows = []
    for sel in row_selectors:
        rows = page.query_selector_all(sel)
        if rows:
            break

    for row in rows:
        cells = row.query_selector_all("td")
        if len(cells) < 2:
            continue
        key = (cells[0].inner_text() or "").strip()
        value = (cells[1].inner_text() or "").strip()
        if key and value and len(key) < 120 and len(value) < 300:
            specs[key] = value

    highlights_text = _try_text(page, [
        "div._1AN87F",
        "div.RmoJbe",
        "div._2cM9lP",
        "ul.G4BRas",
    ])

    spec_text = "\n".join(
        [highlights_text] + [f"{k}: {v}" for k, v in specs.items()]
    ).strip()
    return spec_text, specs


def search_flipkart_products(query_parts: list[str], max_results: int) -> list[ProductCandidate]:
    query = build_search_query(query_parts)
    search_url = f"{FLIPKART_BASE_URL}/search?q={query}"
    candidates: list[ProductCandidate] = []
    logger.info(f"[Flipkart] Search started | max={max_results}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = open_context(browser)
        page = context.new_page()
        page.goto(search_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
        page.wait_for_timeout(2500)

        # Close login popup if present
        for close_sel in ["button._2KpZ6l._2doB4z", "button._2doB4z", "span._30XB9F"]:
            close_button = page.query_selector(close_sel)
            if close_button:
                try:
                    close_button.click(timeout=1500)
                except Exception:
                    pass
                break

        listing_items = _flipkart_listing_links(page, max_results=max_results)
        logger.info(f"[Flipkart] Listing links found: {len(listing_items)}")

        for item in listing_items:
            polite_delay()
            product_page = context.new_page()
            try:
                logger.info(f"[Flipkart] Visiting: {item['url']}")
                product_page.goto(item["url"], wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
                # Wait for spec table or highlights to render
                try:
                    product_page.wait_for_selector(
                        "div._14cfVK, div.GNOMPZ, div._2TID2M, div.hGSR34, table, div.RmoJbe",
                        timeout=8000,
                    )
                except Exception:
                    pass
                product_page.wait_for_timeout(1500)

                name = _flipkart_extract_name(product_page, item["title"])
                price_text = _flipkart_extract_price(product_page)
                specs_text, specs_map = _flipkart_extract_specs(product_page)

                # Enrich specs_text with name so hard-filter has data even if specs are sparse
                if not specs_text:
                    specs_text = name

                candidates.append(
                    ProductCandidate(
                        platform="Flipkart",
                        name=name,
                        url=item["url"],
                        price_text=price_text,
                        price_inr=clean_price_to_inr(price_text),
                        specs_text=specs_text,
                        specs_map=specs_map,
                    )
                )
                logger.info(f"[Flipkart] Added: {name[:80]}")
            except Exception:
                continue
            finally:
                product_page.close()

        context.close()
        browser.close()

    logger.info(f"[Flipkart] Search done | candidates={len(candidates)}")
    return candidates
