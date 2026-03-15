import re

from src.llm_client import invoke_structured
from src.schemas import ProcurementRequest


def _rule_based_category(text: str) -> str:
    low = text.lower()
    if "laptop" in low or "notebook" in low:
        return "laptop"
    if "monitor" in low or "display" in low:
        return "monitor"
    return "other"


def _rule_based_parse(text: str) -> ProcurementRequest:
    low = text.lower()

    def _int(pattern: str) -> int | None:
        m = re.search(pattern, low)
        return int(m.group(1)) if m else None

    def _float(pattern: str) -> float | None:
        m = re.search(pattern, low)
        return float(m.group(1)) if m else None

    def _money(pattern: str) -> float | None:
        m = re.search(pattern, low)
        return float(m.group(1).replace(",", "")) if m else None

    brands_allowed = [
        brand.title()
        for brand in ["asus", "samsung", "hp", "dell", "lenovo", "acer"]
        if brand in low
    ]

    cpu_min_generation = _int(r"(\d{2})(?:st|nd|rd|th)?\s*gen")
    ram_gb_exact = _int(r"(\d{1,3})\s*gb\s*ram")
    storage_gb_ssd_exact = _int(r"(\d{3,4})\s*gb\s*ssd")
    screen_size_inch_exact = _float(r"(\d{1,2}(?:\.\d+)?)\s*(?:inch|inches|\")")
    price_max_inr = _money(r"(?:under|below|less than)\s*₹?\s*([\d,]+)")

    cpu_family = "Intel Core i5" if "i5" in low else None
    resolution = "4K" if "4k" in low else None
    panel_type = "IPS" if "ips" in low else None

    return ProcurementRequest(
        raw_text=text,
        category=_rule_based_category(text),
        brands_allowed=brands_allowed,
        cpu_family=cpu_family,
        cpu_min_generation=cpu_min_generation,
        ram_gb_exact=ram_gb_exact,
        storage_gb_ssd_exact=storage_gb_ssd_exact,
        screen_size_inch_exact=screen_size_inch_exact,
        resolution=resolution,
        panel_type=panel_type,
        price_max_inr=price_max_inr,
    )


def parse_procurement_request(request_text: str) -> ProcurementRequest:
    system_prompt = """
Extract procurement constraints from user text.
Rules:
- Infer category from context (laptop/monitor/other).
- Keep only explicit constraints.
- Use null for unknown values and [] for empty brand list.
- Do not populate raw_text.
""".strip()

    user_prompt = f"Request:\n{request_text}"

    try:
        parsed, _provider = invoke_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=ProcurementRequest,
        )
        data = parsed.model_dump()
        data["raw_text"] = request_text
        data["category"] = str(data.get("category") or _rule_based_category(request_text)).lower()
        data["brands_allowed"] = data.get("brands_allowed") or []
        return ProcurementRequest(**data)
    except Exception:
        return _rule_based_parse(request_text)
