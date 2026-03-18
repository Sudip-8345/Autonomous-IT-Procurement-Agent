from src.llm_client import invoke_structured
from src.schemas import ProcurementRequest


def parse_procurement_request(request_text: str) -> ProcurementRequest:
    system_prompt = """
Extract procurement constraints from user text.
Rules:
- Infer category from context. Keep it flexible for any IT hardware (e.g., laptop, monitor, ups, server, rack server, network switch, router, storage, firewall, accessories, other).
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
        data["category"] = str(data.get("category") or "other").lower()
        data["brands_allowed"] = data.get("brands_allowed") or []
        return ProcurementRequest(**data)
    except Exception:
        return ProcurementRequest(raw_text=request_text, category="other", brands_allowed=[])
