import random
import re
import time
from urllib.parse import quote_plus

from playwright.sync_api import BrowserContext, Page

from src.config import REQUEST_DELAY_SECONDS
from src.config import USER_AGENT

# To prevent bot detection
def polite_delay(multiplier: float = 1.0) -> None:
    base = REQUEST_DELAY_SECONDS * multiplier
    jitter = random.uniform(0.25, 0.9)
    time.sleep(base + jitter)


def clean_price_to_inr(price_text: str | None) -> float | None:
    if not price_text:
        return None

    text = price_text.replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None

    try:
        return float(match.group(1))
    except Exception:
        return None


def build_search_query(query_parts: list[str]) -> str:
    phrase = " ".join(part.strip() for part in query_parts if part and part.strip())
    return quote_plus(phrase)


def text_or_empty(page: Page, selector: str) -> str:
    try:
        node = page.query_selector(selector)
        if not node:
            return ""
        return (node.inner_text() or "").strip()
    except Exception:
        return ""


def collect_table_specs(page: Page, row_selector: str, key_selector: str, val_selector: str) -> dict[str, str]:
    specs: dict[str, str] = {}
    try:
        rows = page.query_selector_all(row_selector)
        for row in rows:
            key_node = row.query_selector(key_selector)
            val_node = row.query_selector(val_selector)
            if not key_node or not val_node:
                continue
            key = (key_node.inner_text() or "").strip()
            val = (val_node.inner_text() or "").strip()
            if key and val:
                specs[key] = val
    except Exception:
        return specs

    return specs


def open_context(browser) -> BrowserContext:
    return browser.new_context(
        viewport={"width": 1400, "height": 900},
        user_agent=USER_AGENT,
    )
