import gradio as gr

from src.agent import run_procurement_agent
from src.demo_requests import REQUEST_1, REQUEST_2


def _render(out: dict) -> str:
    items = out.get("verified_products", [])
    steps = out.get("steps", [])
    head = (
        f"Candidates: **{out.get('total_candidates', 0)}** | "
        f"Rejected: **{out.get('rejected_candidates', 0)}** | "
        f"Approved: **{len(items)}**"
    )
    step_text = "\n".join(f"- {s}" for s in steps)
    errs = "\n".join(f"- ⚠️ {e}" for e in out.get("errors", []))
    rows = []
    for x in items:
        specs = ", ".join(f"{k}: {v}" for k, v in x.get("key_matching_specs", {}).items())
        row = f"- **{x['product_name']}** | {x['price']} | {x['source_platform']} | [Link]({x['product_url']})"
        rows.append(row + (f"\n  - {specs}" if specs else ""))
    body = "\n\n".join(rows) if rows else "_No strict matches found._"
    return "\n\n".join([head, "### Steps", step_text, errs, body]).strip()


def run(request_text: str, max_results: int):
    print("[UI-Gradio] Running")
    out = run_procurement_agent(request_text, max_results_per_platform=max_results)
    print("[UI-Gradio] Done")
    return out.get("parsed_request", {}), _render(out)


with gr.Blocks(title="Autonomous IT Procurement Agent") as app:
    gr.Markdown("# Autonomous IT Procurement Agent\nSearch and verify IT hardware from Amazon and Flipkart.")
    request = gr.Textbox(label="IT Hardware Procurement Request", value=REQUEST_1, lines=8)
    max_results = gr.Slider(label="Max products/platform", minimum=3, maximum=15, value=8, step=1)
    run_btn = gr.Button("Run")
    demo_btn = gr.Button("Run Demo 2")
    parsed = gr.JSON(label="Parsed Request")
    result = gr.Markdown(label="Results")

    run_btn.click(run, [request, max_results], [parsed, result])
    demo_btn.click(lambda m: run(REQUEST_2, int(m)), [max_results], [parsed, result])


if __name__ == "__main__":
    app.launch()
