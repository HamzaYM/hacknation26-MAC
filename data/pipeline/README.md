# Data Pipeline (Owner: J)

Real data in, deterministic benchmarks out. Everything here is **code, not LLM** (PRD §7):
the agent's every citable number is produced by this pipeline.

```
fetch_cms.py   → data/raw/cms/...        (Medicare rates — the anchor)
fetch_mrf.py   → data/raw/mrf/...        (hospitals' own posted prices — the confrontation number)
transform.py   → data/seed/benchmarks.json  (+ loads into Supabase `benchmarks`)
```

## Stage 1 — Acquire

**CMS Medicare rates** (`fetch_cms.py`) *(web-verified 2026-07)*
- Physician Fee Schedule: PFS Relative Value Files, quarterly ZIP (current release RVU26A at
  cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files/rvu26a) →
  payment = RVU total × conversion factor (**2026 CF ≈ $33.40 non-QP** — use unless the provider
  is an APM participant), locality-adjusted via the GPCI file (NC locality). Shortcut that's fine
  for the demo: the PFS Look-Up Tool (cms.gov/medicare/physician-fee-schedule/search) per demo
  CPT, entered into a small CSV.
- Facility side (ER visit): OPPS Addendum B (APC payment rates) — same approach, demo codes only.

**Hospital MRFs** (`fetch_mrf.py`) *(web-verified 2026-07)*
- CMS price-transparency machine-readable files (45 CFR §180), CMS v2.x schema:
  per code → gross charge, **discounted cash price**, payer-specific negotiated, de-identified min/max.
- **Build on these two** (real static URLs confirmed): **Atrium Health** — per-facility CSVs on Azure blob
  storage, index at atriumhealth.org/for-patients-visitors/financial-assistance/pricing;
  **Novant Health** — JSON (19/20 facilities), file index at
  www2.novanthealth.org/Public_Files/regulatory/cms-hpt.txt. UNC/Duke publish too but are
  403-walled or click-through vendor exports — stretch/manual only.
- These are BIG (100MB–GB). Stream-filter to our demo CPT list only; never commit raw files.

## Stage 2 — Clean (the unglamorous 80%)

- Key normalization: CPT vs HCPCS vs internal charge codes; strip modifiers (`99283-25` → `99283`, keep modifier col).
- Setting split: professional vs facility rates — tag rows, don't average across settings.
- Unit normalization: per-unit vs per-visit; drop rows with units ≤ 0 or price ≤ $0.
- Outlier policy: negotiated rates < 20% of Medicare or > 20× Medicare are data errors — drop, log count.
- Dedup: same hospital+code+payer keep latest file date.
- Every dropped row is logged: `transform.py --report` prints a data-quality summary (rows in/out, drop reasons).

## Stage 3 — Transform (deterministic math)

Per demo CPT: `medicare_rate` (professional + facility where applicable), `mrf_cash`,
`mrf_negotiated_median` (median across collected payer rates), `fh_estimate`
(FAIR Health is paywalled → estimate ≈ 2.54× Medicare [RAND commercial norm], **always labeled
"estimated"**), `band_low/high` = Medicare × config multiples (1.5 / 2.5 from
`config/verticals/medical_bills.yaml`). Output validates against `contracts/benchmark_row.schema.json`.

## Stage 4 — Validate (gate before anyone integrates)

`transform.py --check` asserts, against `data/seed/demo_answer_key.json`:
- every CPT on the demo bill has a benchmark row;
- Medicare total across demo codes = **$438.00** (the number the demo script speaks);
- MRF cash total = **$1,890.00**;
- every seeded flag's dollar impact resolves (duplicate $412, upcode $890, unbundle $642, EOB mismatch $412);
- arithmetic holds: 4287 − 412 = 3875; 1650/4287 → −61.5% (say "−62%").

**`benchmarks_v0.json` is a hand-seeded placeholder shaped like real output** so integration
starts at H3 — replace its values with pipeline output by H5, keeping the totals identical
(or update the answer key + PRD §10.3 + demo script together, never one alone).

## Also owned here
- `demo_answer_key.json` — seeded flags + expected asks + the negotiation arc.
- `ncci_pairs.json` — unbundle pairs for the demo codes.
- Synthetic bill + EOB PDFs (`data/demo_docs/`) — author with the answer key open; every error findable.
- `extraction_prompt.md` — the OpenAI vision prompt turning bill/EOB PDFs into JobSpec line items.
- Statute pack contents in `config/verticals/medical_bills.yaml` + citable strings (NSA, §501(r), GFE).
