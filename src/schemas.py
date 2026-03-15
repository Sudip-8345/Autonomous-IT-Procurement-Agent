from typing import Any
from pydantic import BaseModel, Field

# 
class ProcurementRequest(BaseModel):
    raw_text: str = ""
    category: str = Field(default="other", description="laptop/monitor/other")

    brands_allowed: list[str] = Field(default_factory=list)

    cpu_family: str | None = None
    cpu_min_generation: int | None = None

    ram_gb_exact: int | None = None
    storage_gb_ssd_exact: int | None = None

    screen_size_inch_exact: float | None = None
    resolution: str | None = None
    panel_type: str | None = None

    price_max_inr: float | None = None


class ProductCandidate(BaseModel):
    platform: str
    name: str
    url: str
    price_text: str | None = None
    price_inr: float | None = None
    specs_text: str = ""
    specs_map: dict[str, str] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    approved: bool
    reasons: list[str] = Field(default_factory=list)
    matched_specs: dict[str, Any] = Field(default_factory=dict)


class VerifiedProduct(BaseModel):
    product_name: str
    price: str
    key_matching_specs: dict[str, Any]
    product_url: str
    source_platform: str
