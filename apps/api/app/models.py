"""Pydantic mirrors of contracts/*.schema.json.

The JSON Schemas in /contracts are the source of truth (frozen per PRD §12);
these mirrors exist so FastAPI validates payloads. If you change a contract,
change it in /contracts FIRST, then here, then in apps/web/lib/types.ts.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    cpt: str
    description: Optional[str] = None
    date_of_service: Optional[str] = None
    units: int = 1
    billed_amount: Optional[float] = None
    allowed_amount: Optional[float] = None
    plan_paid: Optional[float] = None
    patient_responsibility: Optional[float] = None
    billing_entity: Optional[str] = None
    dx_codes: list[str] = Field(default_factory=list)  # ICD-10; feeds the upcode dx rule


class DerivedFlag(BaseModel):
    # Flag taxonomy mirrors contracts/scenario.schema.json expected_flags[].type
    # (generalized-pipeline decision #13). "nsa" kept as a back-compat alias for
    # the earlier config knob; "nsa_balance_billing" is the emitted type.
    type: Literal[
        "duplicate", "upcode", "unbundle", "phantom", "markup",
        "eob_mismatch", "nsa", "nsa_balance_billing", "denial",
        "units_error", "absent_from_chargemaster",
    ]
    cpt: Optional[str] = None
    evidence: dict = Field(default_factory=dict)
    dollar_impact: float


class Entity(BaseModel):
    name: str
    kind: Literal["facility", "er_physician_group", "radiology", "anesthesia", "pathology", "collections"]
    balance: Optional[float] = None
    phone: Optional[str] = None


class Bill(BaseModel):
    facility_name: str
    nonprofit_status: bool = False
    statement_date: Optional[str] = None
    due_date: Optional[str] = None
    account_number: str
    is_itemized: bool = True
    total_billed: Optional[float] = None
    patient_balance: Optional[float] = None
    line_items: list[LineItem] = Field(default_factory=list)


class Eob(BaseModel):
    claim_number: Optional[str] = None
    patient_responsibility_total: Optional[float] = None
    denial_codes: list[str] = Field(default_factory=list)
    line_items: list[LineItem] = Field(default_factory=list)


class JobSpec(BaseModel):
    case_id: str
    patient: dict
    insurance: dict = Field(default_factory=dict)
    financial_profile: dict = Field(default_factory=dict)
    authorizations: dict = Field(default_factory=dict)
    bill: Bill
    eob: Eob
    derived_flags: list[DerivedFlag] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)


class BenchmarkRow(BaseModel):
    cpt: str
    description: Optional[str] = None
    medicare_rate: float
    fh_estimate: Optional[float] = None  # always rendered as "estimated" in UI
    mrf_cash: Optional[float] = None
    mrf_negotiated_median: Optional[float] = None
    band_low: float
    band_high: float
    source_url: Optional[str] = None


class Lever(BaseModel):
    id: str
    armed: bool
    armed_by: Optional[str] = None
    citation: Optional[str] = None
    dollar_ask: Optional[float] = None


class StrategyDossier(BaseModel):
    case_id: str
    target_entity: str
    route: Literal["provider", "collections"]
    levers: list[Lever]
    anchor: float
    target: float
    floor: float
    citations: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    # 501(r) account-age clock (26 CFR 1.501(r)-6) — additive routing signals.
    days_since_first_statement: Optional[int] = None
    inside_501r_window: Optional[bool] = None  # nonprofit-only; None when N/A
    # Dual-framing ask surface (decision #10), populated from a BenchmarkReport
    # when one is available. Both optional/None so every existing consumer of
    # StrategyDossier is unaffected (generalized-pipeline WS2).
    ask_table: Optional[list] = None      # per-line billed / medicare× / fair band / excess
    band_framing: Optional[dict] = None   # total-level anchor/target/floor + multiples


class CallOutcome(BaseModel):
    call_id: str
    outcome_type: Literal[
        "reduction", "payment_plan", "charity_app_initiated", "callback", "documented_decline"
    ]
    original_amount: Optional[float] = None
    final_amount: Optional[float] = None
    reduction_pct: Optional[float] = None  # computed by code, never the LLM
    winning_lever: Optional[str] = None
    reference_number: Optional[str] = None
    rep_name: Optional[str] = None
    agreed_action: Optional[str] = None
    next_action_date: Optional[str] = None
    decline_reason: Optional[str] = None
    payment_plan_terms: Optional[dict] = None
    evidence_event_ids: list[int] = Field(default_factory=list)
