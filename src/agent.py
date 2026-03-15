from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import re
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from src.config import DEFAULT_MAX_RESULTS_PER_PLATFORM
from src.evaluator import evaluate_product
from src.request_parser import parse_procurement_request
from src.schemas import VerifiedProduct
from src.scrapers.amazon import search_amazon_products
from src.scrapers.flipkart import search_flipkart_products


class AgentState(TypedDict, total=False):
    request_text: str
    max_results_per_platform: int
    parsed_request: Any
    query_parts: list
    candidates: list
    errors: list
    steps: list
    verified_products: list
    rejected_candidates: int


def _build_graph():
    graph = StateGraph(AgentState)

    def _step(state: dict, message: str) -> list[str]:
        print(message, flush=True)
        return [*state.get("steps", []), message]

    def parse_request(state: dict) -> dict:
        steps = _step(state, "[Agent] Step 1/3: Parsing request")
        req = parse_procurement_request(state["request_text"])
        values = req.model_dump()
        parts = [str(v).strip() for k, v in values.items() if k != "raw_text" and v not in (None, "", [])]
        if isinstance(values.get("brands_allowed"), list):
            parts.extend(str(x).strip() for x in values["brands_allowed"] if str(x).strip())
        query_parts = list(OrderedDict((p.lower(), p) for p in parts).values()) or [req.raw_text]
        steps.append(f"[Agent] Parsed request. Query parts: {len(query_parts)}")
        return {"parsed_request": req, "query_parts": query_parts, "errors": [], "steps": steps}

    def search_tools(state: dict) -> dict:
        steps = _step(state, "[Agent] Step 2/3: Running Amazon + Flipkart search")
        query = state["query_parts"]
        limit = state.get("max_results_per_platform", DEFAULT_MAX_RESULTS_PER_PLATFORM)
        errors = list(state.get("errors", []))
        all_items = []
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = {
                "Amazon": pool.submit(search_amazon_products, query, limit),
                "Flipkart": pool.submit(search_flipkart_products, query, limit),
            }
            for platform, job in jobs.items():
                try:
                    found = job.result()
                    all_items.extend(found)
                    steps.append(f"[Agent] {platform}: {len(found)} candidates")
                except Exception as exc:
                    errors.append(f"{platform} search failed: {exc}")
                    steps.append(f"[Agent] {platform}: failed")
        by_url = OrderedDict((item.url, item) for item in all_items)
        steps.append(f"[Agent] Deduplicated total: {len(by_url)}")
        return {"candidates": list(by_url.values()), "errors": errors, "steps": steps}

    def evaluate_and_sort(state: dict) -> dict:
        steps = _step(state, "[Agent] Step 3/3: Evaluating and sorting products")
        req = state["parsed_request"]
        verified, rejected = [], 0
        for product in state.get("candidates", []):
            verdict = evaluate_product(req, product)
            if verdict.approved:
                verified.append(
                    VerifiedProduct(
                        product_name=product.name,
                        price=product.price_text or "N/A",
                        key_matching_specs=verdict.matched_specs,
                        product_url=product.url,
                        source_platform=product.platform,
                    )
                )
            else:
                rejected += 1

        def price_key(item: VerifiedProduct) -> float:
            m = re.search(r"(\d[\d,]*(?:\.\d+)?)", item.price or "")
            return float(m.group(1).replace(",", "")) if m else 10**12

        verified.sort(key=price_key)
        steps.append(f"[Agent] Approved: {len(verified)} | Rejected: {rejected}")
        return {"verified_products": verified, "rejected_candidates": rejected, "steps": steps}

    graph.add_node("parse_request", parse_request)
    graph.add_node("search_tools", search_tools)
    graph.add_node("evaluate_and_sort", evaluate_and_sort)
    graph.set_entry_point("parse_request")
    graph.add_edge("parse_request", "search_tools")
    graph.add_edge("search_tools", "evaluate_and_sort")
    graph.add_edge("evaluate_and_sort", END)
    return graph.compile()


_PROCUREMENT_GRAPH = _build_graph()


def run_procurement_agent(request_text: str, max_results_per_platform: int | None = None) -> dict[str, Any]:
    print("[Agent] Run started", flush=True)
    out = _PROCUREMENT_GRAPH.invoke(
        {
            "request_text": request_text,
            "max_results_per_platform": max_results_per_platform or DEFAULT_MAX_RESULTS_PER_PLATFORM,
            "steps": [],
        }
    )
    parsed = out.get("parsed_request")
    verified = out.get("verified_products", [])
    candidates = out.get("candidates", [])
    return {
        "parsed_request": parsed.model_dump() if parsed else {},
        "query_parts": out.get("query_parts", []),
        "total_candidates": len(candidates),
        "rejected_candidates": out.get("rejected_candidates", 0),
        "verified_products": [x.model_dump() for x in verified],
        "errors": out.get("errors", []),
        "steps": out.get("steps", []),
    }


