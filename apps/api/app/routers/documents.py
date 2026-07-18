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

from .. import db, storage
from ..config import load_vertical
from ..engine.flags import detect_flags
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
- billed_amount: the "Billed" column as a number
- dx_codes: always an empty array
total_billed = the billed TOTALS amount. patient_responsibility_total = the
"YOUR TOTAL RESPONSIBILITY" amount. Numbers only, exactly as printed."""


def _schema(kind: str) -> dict:
    balance_key = "patient_balance" if kind == "bill" else "patient_responsibility_total"
    return {
        "name": f"{kind}_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "line_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "cpt": {"type": "string"},
                            "description": {"type": "string"},
                            "date_of_service": {"type": "string"},
                            "billed_amount": {"type": "number"},
                            "dx_codes": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["cpt", "description", "date_of_service",
                                     "billed_amount", "dx_codes"],
                        "additionalProperties": False,
                    },
                },
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


def parsed_flags(parsed: dict, kind: str) -> list[DerivedFlag]:
    """Run the real engine over the parsed data (merged into the demo JobSpec)."""
    raw = copy.deepcopy(DEMO_JOB_SPEC)
    if kind == "bill":
        raw["bill"]["line_items"] = parsed.get("line_items") or []
        raw["bill"]["total_billed"] = parsed.get("total_billed")
        raw["bill"]["patient_balance"] = parsed.get("patient_balance")
    else:
        raw["eob"]["line_items"] = parsed.get("line_items") or []
        raw["eob"]["patient_responsibility_total"] = parsed.get("patient_responsibility_total")
    spec = JobSpec.model_validate(raw)
    return detect_flags(spec, load_vertical(), demo_benchmarks())


@router.post("/parse")
async def parse_document(file: UploadFile = File(...), kind: str = Form(...),
                         case_id: str = Form("demo")) -> dict:
    if kind not in ("bill", "eob"):
        raise HTTPException(422, "kind must be 'bill' or 'eob'")
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(422, "empty file")

    parsed, model = extract_pdf(pdf_bytes, kind)
    try:
        flags = parsed_flags(parsed, kind)
    except ValueError as err:  # pydantic rejected the extraction shape
        log.warning("parsed %s failed JobSpec validation: %s", kind, type(err).__name__)
        flags = []
    reconciliation = reconcile_bill(parsed) if kind == "bill" else reconcile_eob(parsed)

    document_id = str(uuid.uuid4())
    resolved_case = DEMO_CASE_ID if case_id in ("demo", DEMO_CASE_ID) else case_id
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
