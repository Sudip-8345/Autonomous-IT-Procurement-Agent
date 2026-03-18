from urllib.parse import urljoin
import logging
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth.stealth import Stealth

from src.config import AMAZON_BASE_URL, DEFAULT_TIMEOUT_MS
from src.schemas import ProductCandidate
from src.scrapers.utils import (
    build_search_query,
    clean_price_to_inr,
    open_context,
    polite_delay,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _txt(node) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _amazon_listing_links(page_html: str, max_results: int) -> list[dict[str, str]]:
    soup = BeautifulSoup(page_html, "lxml")
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    rows = soup.select("div.s-result-item[data-component-type='s-search-result']")

    for row in rows:
        row_text = _txt(row).lower()
        if "sponsored" in row_text:
            continue

        dp_links = row.select("a[href*='/dp/']")
        if not dp_links: # No product link found in this row
            continue

        title = (
            _txt(row.select_one("h2"))
            or _txt(row.select_one("h2 span"))
            or _txt(row.select_one("[data-cy='title-recipe']"))
            or _txt(row.select_one("span.a-size-medium.a-color-base.a-text-normal"))
            or _txt(row.select_one("a.a-link-normal.s-line-clamp-2.s-link-style.a-text-normal"))
        )

        link_node = dp_links[0]
        href = (link_node.get("href") or "").strip()
        if not href:
            continue

        url = urljoin(AMAZON_BASE_URL, href.split("?")[0])
        if "/dp/" not in url or url in seen:
            continue

        if not title:
            title = _txt(link_node)

        seen.add(url)
        items.append({"title": title, "url": url})
        if len(items) >= max_results:
            break

    return items


def _amazon_extract_specs_from_html(product_html: str) -> tuple[str, dict[str, str], str, str]:
    soup = BeautifulSoup(product_html, "lxml")
    specs: dict[str, str] = {}

    title = _txt(soup.select_one("#productTitle")).strip('"')

    price = (
        _txt(soup.select_one("span.a-price span.a-price-whole"))
        or _txt(soup.select_one("#corePrice_feature_div .a-offscreen"))
        or _txt(soup.select_one(".a-price .a-offscreen"))
        or _txt(soup.select_one("#priceblock_ourprice"))
        or _txt(soup.select_one("#priceblock_dealprice"))
    )
    if price and not price.startswith("₹"):
        price = f"₹{price}"

    for row in soup.select("#productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr, #technicalSpecifications_feature_div tr"):
        key_node = row.select_one("th") # table header as key
        val_node = row.select_one("td") # table data as value
        key = _txt(key_node).rstrip(":")
        val = _txt(val_node)
        if key and val:
            specs[key] = val

    for li in soup.select("#feature-bullets li span.a-list-item"):
        bullet = _txt(li)
        if bullet:
            specs[f"bullet_{len(specs)+1}"] = bullet

    desc_text = _txt(soup.select_one("#productDescription"))
    spec_text = "\n".join(
        [line for line in [title, desc_text] + [f"{k}: {v}" for k, v in specs.items()] if line]
    ).strip()

    return spec_text, specs, title, price


def search_amazon_products(query_parts: list[str], max_results: int) -> list[ProductCandidate]:
    query = build_search_query(query_parts)
    search_url = f"{AMAZON_BASE_URL}/s?k={query}"
    candidates: list[ProductCandidate] = []
    print(f"[Amazon] Search started | max={max_results}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = open_context(browser)
        stealth = Stealth()
        page = context.new_page()
        stealth.apply_stealth_sync(page)

        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=min(DEFAULT_TIMEOUT_MS, 20000))
        except Exception:
            page.goto(search_url, wait_until="commit", timeout=min(DEFAULT_TIMEOUT_MS, 20000))

        page.wait_for_timeout(1200)
        try:
            page.wait_for_selector("div.s-result-item[data-component-type='s-search-result']", timeout=2200)
        except Exception:
            pass

        listing_items = _amazon_listing_links(page.content(), max_results=max_results)
        logger.info(f"[Amazon] Listing links found: {len(listing_items)}")
        if not listing_items:
            context.close()
            browser.close()
            logger.info("[Amazon] No listings found")
            return candidates

        product_page = context.new_page()
        stealth.apply_stealth_sync(product_page)

        for item in listing_items:
            polite_delay(multiplier=0.15)
            try:
                logger.info(f"[Amazon] Visiting: {item['url']}")
                try:
                    product_page.goto(item["url"], wait_until="domcontentloaded", timeout=min(DEFAULT_TIMEOUT_MS, 18000))
                except Exception:
                    product_page.goto(item["url"], wait_until="commit", timeout=min(DEFAULT_TIMEOUT_MS, 18000))

                product_page.wait_for_timeout(700)
                try:
                    product_page.wait_for_selector("#productTitle", timeout=2200)
                except Exception:
                    pass

                specs_text, specs_map, parsed_name, parsed_price = _amazon_extract_specs_from_html(product_page.content())
                name = parsed_name or item["title"]
                price_text = parsed_price
                if not specs_text:
                    specs_text = name or item["title"]

                candidates.append(
                    ProductCandidate(
                        platform="Amazon",
                        name=name,
                        url=item["url"],
                        price_text=price_text,
                        price_inr=clean_price_to_inr(price_text),
                        specs_text=specs_text,
                        specs_map=specs_map,
                    )
                )
                logger.info(f"[Amazon] Added: {name[:80]}")
            except Exception:
                continue

        product_page.close()

        context.close()
        browser.close()

    logger.info(f"[Amazon] Search done | candidates={len(candidates)}")
    return candidates
