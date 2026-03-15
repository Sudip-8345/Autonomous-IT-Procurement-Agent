import asyncio
import sys

import panel as pn

from src.agent import run_procurement_agent
from src.demo_requests import REQUEST_1, REQUEST_2


def _configure_windows_event_loop() -> None:
    if sys.platform != "win32":
        return
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass


_configure_windows_event_loop()
pn.extension()

title = pn.pane.Markdown("# Autonomous IT Procurement Agent\nAmazon + Flipkart sourcing with AI-based verification")
request_input = pn.widgets.TextAreaInput(name="Procurement Request", value=REQUEST_1, height=180)
max_results = pn.widgets.IntSlider(name="Max products/platform", start=3, end=15, value=8)
run_btn = pn.widgets.Button(name="Run", button_type="primary")
demo_btn = pn.widgets.Button(name="Run Demos")
status = pn.pane.Markdown("")
parsed = pn.pane.JSON({}, depth=2)
results = pn.pane.Markdown("", sizing_mode="stretch_width")


def render(title_text: str, out: dict) -> str:
    items = out.get("verified_products", [])
    steps = out.get("steps", [])
    head = f"## {title_text}\nCandidates: **{out.get('total_candidates', 0)}** | Rejected: **{out.get('rejected_candidates', 0)}** | Approved: **{len(items)}**"
    step_text = "\n".join([f"- {s}" for s in steps])
    errs = "\n".join([f"- ⚠️ {e}" for e in out.get("errors", [])])
    rows = []
    for x in items:
        specs = ", ".join([f"{k}: {v}" for k, v in x.get("key_matching_specs", {}).items()])
        row = f"- **{x['product_name']}** | {x['price']} | {x['source_platform']} | [Link]({x['product_url']})"
        rows.append(row + (f"\n  - {specs}" if specs else ""))
    body = "\n\n".join(rows) if rows else "_No strict matches found._"
    return "\n\n".join([head, "### Steps", step_text, errs, body]).strip()


def run_once(text: str, label: str) -> dict:
    print(f"[UI-Panel] Running: {label}", flush=True)
    out = run_procurement_agent(text, max_results_per_platform=max_results.value)
    parsed.object = out.get("parsed_request", {})
    results.object = render(label, out)
    print(f"[UI-Panel] Done: {label}", flush=True)
    return out


def on_run(_):
    status.object = "Running... check steps below and terminal logs"
    run_once(request_input.value, "Result")
    status.object = "Done"


def on_demo(_):
    status.object = "Running demos... check steps below and terminal logs"
    out1 = run_procurement_agent(REQUEST_1, max_results_per_platform=max_results.value)
    out2 = run_procurement_agent(REQUEST_2, max_results_per_platform=max_results.value)
    parsed.object = out1.get("parsed_request", {})
    results.object = render("Request 1 – Laptops", out1) + "\n\n---\n\n" + render("Request 2 – Monitors", out2)
    status.object = "Done"


run_btn.on_click(on_run)
demo_btn.on_click(on_demo)
pn.Column(title, pn.Row(max_results, run_btn, demo_btn), request_input, status, parsed, results).servable()
