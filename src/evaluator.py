from typing import Any

from pydantic import BaseModel, Field

from src.llm_client import invoke_structured
from src.schemas import EvaluationResult, ProcurementRequest, ProductCandidate


class AIEvaluationDecision(BaseModel):
    approved: bool = False
    reasons: list[str] = Field(default_factory=list)
    matched_specs: dict[str, Any] = Field(default_factory=dict)


def evaluate_product(req: ProcurementRequest, product: ProductCandidate) -> EvaluationResult:
    system_prompt = """
You are a strict IT procurement validator.
You are the ONLY decision-maker. No external hard filters exist.
Determine if the product satisfies ALL explicit procurement requirements.

IMPORTANT evaluation rules:
- Evaluate from ALL given product evidence: name, price, specs_text, specs_map, URL.
- Do not guess missing values. If a mandatory requirement is not explicitly evidenced, reject.
- Be strict about exact constraints (brand allowlist, exact RAM/storage, min CPU gen, max price).
- Include concise reasons and matched_specs.

Return JSON only:
{
  "approved": true/false,
  "reasons": ["..."],
  "matched_specs": {"key": "value"}
}
""".strip()

    user_prompt = f"""
Procurement requirements:
{req.model_dump_json(indent=2)}

Product candidate:
{product.model_dump_json(indent=2)}

Decision policy:
- approved=true only when every explicit requirement is satisfied.
- approved=false when any required field is missing, ambiguous, or mismatched.
""".strip()

    try:
        decision, _provider = invoke_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=AIEvaluationDecision,
        )
    except Exception as exc:
        decision = AIEvaluationDecision(
            approved=False,
            reasons=[f"LLM evaluation unavailable: {exc}"],
            matched_specs={},
        )

    return EvaluationResult(
        approved=decision.approved,
        reasons=decision.reasons,
        matched_specs=decision.matched_specs,
    )
