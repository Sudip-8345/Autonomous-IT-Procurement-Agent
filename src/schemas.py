from typing import Any
from pydantic import BaseModel, Field


class ProcurementRequest(BaseModel):
    raw_text: str = ""
    category: str = Field(default="other", description="Flexible IT hardware category (e.g., laptop, monitor, ups, server, switch, router, firewall, storage, accessory, other)")
    item_type: str | None = Field(default=None, description="Primary item type requested")

    brands_allowed: list[str] = Field(default_factory=list)
    quantity: int | None = None
    required_features: list[str] = Field(default_factory=list)
    required_specs: dict[str, Any] = Field(default_factory=dict)
    preferred_specs: dict[str, Any] = Field(default_factory=dict)
    excluded_terms: list[str] = Field(default_factory=list)

    price_max_inr: float | None = None


class ProductCandidate(BaseModel):
    platform: str
    name: str
    url: str
    price_text: str | None = None
    price_inr: float | None = None
    specs_text: str = ""
    specs_map: dict[str, str] = Field(default_factory=dict, description="key-value pairs of specs extracted from the product page")


class EvaluationResult(BaseModel):
    approved: bool
    reasons: list[str] = Field(default_factory=list)
    matched_specs: dict[str, Any] = Field(default_factory=dict)


class VerifiedProduct(BaseModel):
    product_name: str
    price: str
    key_matching_specs: dict[str, Any] = Field(default_factory=dict, description="key-value pairs of specs that match the procurement request")
    product_url: str
    source_platform: str
