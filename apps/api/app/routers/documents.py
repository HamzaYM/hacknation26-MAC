"""POST /documents/parse — bill/EOB PDF upload → OpenAI vision extraction.

Contract (frozen): multipart file + kind (bill|eob) + optional case_id →
{document_id, storage_path, parsed, reconciliation, flags}. The extraction is
reconciled against the fixture DEMO_LINE_ITEMS / DEMO_JOB_SPEC eob totals, and
the REAL engine (engine/flags.py) runs over the parsed data — the LLM never
computes a flag.

Vision models are tried in order (gpt-5.6-terra → gpt-5.6-luna → gpt-4o); the
PDF goes up as a native file input first, falling back to pypdfium2-rasterized
PNG pages if the API rejects file parts. PHI hygiene: we log model names and
line counts, never document contents or keys.
"""
from __future__ import annotations

import base64
import copy
import io
import json
import logging
import uuid

import openai
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import case_store, db, storage
from ..config import load_vertical
from ..engine.flags import detect_flags
from ..engine.lookup import get_lookup
from ..engine.reconcile import reconcile
from ..fixtures import DEMO_CASE_ID, DEMO_JOB_SPEC, DEMO_LINE_ITEMS, demo_benchmarks
from ..models import DerivedFlag, JobSpec

router = APIRouter()
log = logging.getLogger("negotiator.documents")

_MODELS = ("gpt-5.6-terra", "gpt-5.6-luna", "gpt-4o")

_BILL_PROMPT = """\
You are parsing an itemized hospital bill PDF. Extract every charge line exactly as printed,
in order, without merging or deduplicating (if the same code appears twice, output two entries):
- cpt: the CPT/HCPCS code column value
- description: the printed description
- date_of_service: ISO format YYYY-MM-DD
- billed_amount: the line amount as a number (no $ or commas)
- dx_codes: the statement's diagnosis ICD-10 codes (listed in the header, e.g. "Diagnosis: J06.9 ...")
  attached to E/M visit lines only (CPT codes starting 992); an empty array for every other line.
total_billed = the "Total Charges" amount. patient_balance = the "BALANCE DUE" amount
(after insurance payments). Numbers only, exactly as printed."""

_EOB_PROMPT = """\
You are parsing a health-insurance Explanation of Benefits (EOB) PDF. Extract each claim line:
- cpt: the CPT/HCPCS code
- description: the printed description
- date_of_service: ISO format YYYY-MM-DD (use the header Date of Service if lines lack dates)
- units: the quantity/units column as an integer (default 1 if not printed)
- billed_amount: the "Billed"/"Charges" column as a number
- allowed_amount: the "Allowed"/"Plan Allowance" column (the negotiated rate) as a number
- plan_paid: the "Plan Paid"/"Insurance Paid" column as a number (use 0 for denied lines)
- patient_responsibility: the "Patient Responsibility"/"You Owe" column as a number
- dx_codes: always an empty array
total_billed = the billed TOTALS amount. patient_responsibility_total = the
"YOUR TOTAL RESPONSIBILITY" amount. Numbers only, exactly as printed; use 0 (not null)
where a column is present but the amount is zero."""


def _line_item_schema(kind: str) -> dict:
    """Per-line schema. EOB lines additionally carry the adjudication columns
    (units/allowed/plan_paid/patient_responsibility) the reconciler needs — the
    frozen contract (contracts/job_spec.schema.json $defs/line_item) already
    supports them; this is where extraction finally populates them."""
    props: dict = {
        "cpt": {"type": "string"},
        "description": {"type": "string"},
        "date_of_service": {"type": "string"},
        "billed_amount": {"type": "number"},
        "dx_codes": {"type": "array", "items": {"type": "string"}},
    }
    required = ["cpt", "description", "date_of_service", "billed_amount", "dx_codes"]
    if kind == "eob":
        props.update({
            "units": {"type": "integer"},
            "allowed_amount": {"type": "number"},
            "plan_paid": {"type": "number"},
            "patient_responsibility": {"type": "number"},
        })
        required += ["units", "allowed_amount", "plan_paid", "patient_responsibility"]
    return {
        "type": "object", "properties": props,
        "required": required, "additionalProperties": False,
    }


def _schema(kind: str) -> dict:
    balance_key = "patient_balance" if kind == "bill" else "patient_responsibility_total"
    return {
        "name": f"{kind}_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "line_items": {"type": "array", "items": _line_item_schema(kind)},
                "total_billed": {"type": "number"},
                balance_key: {"type": "number"},
            },
            "required": ["line_items", "total_billed", balance_key],
            "additionalProperties": False,
        },
    }


def _file_parts(pdf_bytes: bytes) -> list[dict]:
    b64 = base64.b64encode(pdf_bytes).decode()
    return [{"type": "file",
             "file": {"filename": "document.pdf",
                      "file_data": f"data:application/pdf;base64,{b64}"}}]


def _image_parts(pdf_bytes: bytes) -> list[dict]:
    """Rasterize each page via pypdfium2 → base64 PNG image parts."""
    import pypdfium2 as pdfium

    parts = []
    doc = pdfium.PdfDocument(pdf_bytes)
    for page in doc:
        buf = io.BytesIO()
        page.render(scale=2).to_pil().save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        parts.append({"type": "image_url",
                      "image_url": {"url": f"data:image/png;base64,{b64}"}})
    return parts


def _complete(client: openai.OpenAI, model: str, parts: list[dict], kind: str) -> dict:
    prompt = _BILL_PROMPT if kind == "bill" else _EOB_PROMPT
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, *parts]}],
        response_format={"type": "json_schema", "json_schema": _schema(kind)},
    )
    return json.loads(resp.choices[0].message.content)


def _model_missing(err: Exception) -> bool:
    msg = str(err).lower()
    return "model" in msg and ("does not exist" in msg or "not found" in msg
                               or "invalid model" in msg or "no access" in msg)


def extract_pdf(pdf_bytes: bytes, kind: str) -> tuple[dict, str]:
    """OpenAI vision extraction with model fallback; returns (parsed, model_used)."""
    client = openai.OpenAI()
    parts, rasterized = _file_parts(pdf_bytes), False
    errors = (openai.NotFoundError, openai.BadRequestError)
    for model in _MODELS:
        for _attempt in ("file", "images"):
            try:
                parsed = _complete(client, model, parts, kind)
                log.info("parsed %s with model=%s input=%s (%d lines)", kind, model,
                         "images" if rasterized else "pdf-file", len(parsed.get("line_items") or []))
                return parsed, model
            except errors as err:
                if _model_missing(err):
                    log.info("model %s unavailable, trying next", model)
                    break  # next model
                if rasterized:
                    raise
                log.info("file input rejected, rasterizing pages")
                parts, rasterized = _image_parts(pdf_bytes), True
    raise HTTPException(502, f"no vision model available (tried {', '.join(_MODELS)})")


def _amt(value) -> float | None:
    return None if value is None else round(float(value), 2)


def reconcile_bill(parsed: dict) -> dict:
    """Compare parsed bill lines + totals against the fixture DEMO_LINE_ITEMS."""
    remaining = list(parsed.get("line_items") or [])
    matches, mismatches = 0, []
    for exp in DEMO_LINE_ITEMS:
        # prefer the parsed line matching cpt+amount (disambiguates duplicates), else cpt only
        idx = next((i for i, li in enumerate(remaining) if li.get("cpt") == exp["cpt"]
                    and _amt(li.get("billed_amount")) == _amt(exp["billed_amount"])), None)
        if idx is None:
            idx = next((i for i, li in enumerate(remaining) if li.get("cpt") == exp["cpt"]), None)
        if idx is None:
            mismatches.append({"cpt": exp["cpt"], "field": "line_item",
                               "parsed": None, "expected": exp["billed_amount"]})
            continue
        li, ok = remaining.pop(idx), True
        if _amt(li.get("billed_amount")) != _amt(exp["billed_amount"]):
            mismatches.append({"cpt": exp["cpt"], "field": "billed_amount",
                               "parsed": li.get("billed_amount"), "expected": exp["billed_amount"]})
            ok = False
        if li.get("date_of_service") != exp["date_of_service"]:
            mismatches.append({"cpt": exp["cpt"], "field": "date_of_service",
                               "parsed": li.get("date_of_service"), "expected": exp["date_of_service"]})
            ok = False
        matches += ok
    for li in remaining:  # parsed lines with no fixture counterpart
        mismatches.append({"cpt": li.get("cpt"), "field": "line_item",
                           "parsed": li.get("billed_amount"), "expected": None})
    for field in ("total_billed", "patient_balance"):
        if _amt(parsed.get(field)) != _amt(DEMO_JOB_SPEC["bill"][field]):
            mismatches.append({"cpt": None, "field": field,
                               "parsed": parsed.get(field), "expected": DEMO_JOB_SPEC["bill"][field]})
    verdict = "exact" if not mismatches else ("partial" if matches else "failed")
    return {"verdict": verdict, "matches": matches, "mismatches": mismatches}


def reconcile_eob(parsed: dict) -> dict:
    """Compare parsed EOB totals against the fixture JobSpec eob."""
    expected = DEMO_JOB_SPEC["eob"]["patient_responsibility_total"]
    got = parsed.get("patient_responsibility_total")
    if _amt(got) == _amt(expected):
        return {"verdict": "exact", "matches": 1, "mismatches": []}
    return {"verdict": "failed", "matches": 0,
            "mismatches": [{"cpt": None, "field": "patient_responsibility_total",
                            "parsed": got, "expected": expected}]}


def _empty_case_spec(case_id: str) -> dict:
    """Skeleton JobSpec for a brand-new case (no fixture) — bill+EOB filled in as
    documents are uploaded. Kills the deepcopy(DEMO_JOB_SPEC) merge for real cases;
    the Maya demo case still gets the fixture via case_store's DEMO_CASE_ID fallback."""
    return {
        "case_id": case_id,
        "patient": {},
        "insurance": {},
        "financial_profile": {},
        "authorizations": {},
        "bill": {"facility_name": "", "account_number": "", "line_items": []},
        "eob": {"line_items": []},
        "entities": [{"name": "the provider", "kind": "facility"}],
    }


def _base_job_spec(case_id: str) -> dict:
    """The case's accumulated JobSpec dict: the stored one, else the Maya fixture
    for DEMO_CASE_ID (via case_store), else a fresh skeleton."""
    spec = case_store.get_job_spec(case_id)
    return spec if spec is not None else _empty_case_spec(case_id)


def _splice(raw: dict, parsed: dict, kind: str) -> dict:
    """Merge a freshly parsed bill or EOB into a case JobSpec dict (in place)."""
    if kind == "bill":
        raw["bill"]["line_items"] = parsed.get("line_items") or []
        raw["bill"]["total_billed"] = parsed.get("total_billed")
        raw["bill"]["patient_balance"] = parsed.get("patient_balance")
    else:
        raw["eob"]["line_items"] = parsed.get("line_items") or []
        raw["eob"]["patient_responsibility_total"] = parsed.get("patient_responsibility_total")
    return raw


def parsed_flags(parsed: dict, kind: str, case_id: str = DEMO_CASE_ID, lookup=None) -> list[DerivedFlag]:
    """Run the real engine over the case's accumulated data. The base spec comes
    from case_store (Maya's fixture for DEMO_CASE_ID; the real accumulated spec for
    any other case) — never a hardcoded deepcopy of the demo fixture."""
    raw = _splice(copy.deepcopy(_base_job_spec(case_id)), parsed, kind)
    spec = JobSpec.model_validate(raw)
    return detect_flags(spec, load_vertical(), demo_benchmarks(), lookup=lookup)


def case_reconciliation(case_id: str, parsed: dict, kind: str) -> dict:
    """Real bill<->EOB reconciliation (engine/reconcile.py) once both documents
    exist for a case; otherwise a 'pending counterpart' status. Shape carries a
    `verdict` so the response contract stays stable across the demo and real paths."""
    raw = _splice(copy.deepcopy(_base_job_spec(case_id)), parsed, kind)
    spec = JobSpec.model_validate(raw)
    has_bill = bool(spec.bill.line_items)
    has_eob = bool(spec.eob.line_items) or spec.eob.patient_responsibility_total is not None
    if has_bill and has_eob:
        result = reconcile(spec.bill, spec.eob)
        result["verdict"] = "reconciled"
        return result
    missing = "eob" if kind == "bill" else "bill"
    return {"verdict": "pending_counterpart", "detail": f"no {missing} uploaded for this case yet",
            "matched": [], "bill_only": [], "eob_only": [], "totals": {}, "self_pay": False}


@router.post("/parse")
async def parse_document(file: UploadFile = File(...), kind: str = Form(...),
                         case_id: str = Form("demo")) -> dict:
    if kind not in ("bill", "eob"):
        raise HTTPException(422, "kind must be 'bill' or 'eob'")
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(422, "empty file")

    parsed, model = extract_pdf(pdf_bytes, kind)
    resolved_case = DEMO_CASE_ID if case_id in ("demo", DEMO_CASE_ID) else case_id
    is_demo = resolved_case == DEMO_CASE_ID

    try:
        flags = parsed_flags(parsed, kind, resolved_case, lookup=get_lookup())
    except ValueError as err:  # pydantic rejected the extraction shape
        log.warning("parsed %s failed JobSpec validation: %s", kind, type(err).__name__)
        flags = []

    # Accumulate the parsed doc into the case (real cases only — the Maya demo
    # case stays backed by the pristine fixture so existing demo consumers hold).
    if not is_demo:
        try:
            case_store.put(resolved_case, "job_spec",
                           _splice(copy.deepcopy(_base_job_spec(resolved_case)), parsed, kind))
        except Exception as err:  # never let case bookkeeping break the parse response
            log.warning("case_store update skipped: %s", type(err).__name__)

    # Reconciliation: the demo keeps the fixture QA diff (grades the extraction);
    # real cases get true bill<->EOB reconciliation once both docs are present.
    if is_demo:
        reconciliation = reconcile_bill(parsed) if kind == "bill" else reconcile_eob(parsed)
    else:
        reconciliation = case_reconciliation(resolved_case, parsed, kind)

    document_id = str(uuid.uuid4())
    path = f"{resolved_case}/{document_id}.pdf"
    stored = storage.store_document(path, pdf_bytes)  # best-effort, like recordings
    storage_path = stored or f"documents/{path}"
    if resolved_case == DEMO_CASE_ID:
        db.ensure_demo_case()
    db.insert_document(document_id, resolved_case, kind, storage_path, parsed)
    log.info("document %s stored=%s model=%s verdict=%s", document_id, bool(stored),
             model, reconciliation["verdict"])
    return {
        "document_id": document_id,
        "storage_path": storage_path,
        "parsed": parsed,
        "reconciliation": reconciliation,
        "flags": [f.model_dump() for f in flags],
    }
