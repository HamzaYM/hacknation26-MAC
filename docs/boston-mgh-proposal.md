# PROPOSAL (for Hamza) — adopt real MGH price-transparency numbers for the demo

**Status: proposal, not landed.** This touches the locked demo numbers (decision log:
"MRF cash $1,890 … change ONLY together") and Hamza's merged engine, so per ORCHESTRATION
rule 2 it's his call. Nothing in the PR that carries this doc changes the locked numbers —
the demo still runs on the synthetic $1,890 seed and all 27 engine tests stay green. This
is the "should we upgrade the demo to real data?" ask.

## The opportunity

We have Mass General Brigham / MGH's real, published CMS price-transparency file
(`042697983_Massachusetts-General-Hospital_StandardCharges.csv`, ~60MB, 159k rows) and a
working extractor (`data/pipeline/mrf_extract.py`, **already landed and MGH-verified** in
this PR). Pointing the demo's benchmark seed at real MGH numbers would make "your own
posted cash price is …" a genuinely real, checkable figure instead of a synthetic placeholder
— a stronger honesty story for judges.

## The real numbers (computed, deterministic)

| Figure | Locked (synthetic) | Real MGH | Note |
|---|---|---|---|
| MRF cash total (5 demo CPTs) | $1,890.00 | **$2,633.25** | discounted cash price, real |
| Commercial negotiated median total | ~$2,600 | **$999.30** | commercial-payer weighted median; insurers pay *below* cash — a stronger fairness line |
| Medicare total | $438.00 | (still needs real MA PFS) | flagged `TODO(Jay-verify)` either way |

Per-CPT (setting=outpatient, commercial-only medians): 99283 cash 1409.25 / neg 328.79 ·
71046 354.00 / 180.78 · 80053 133.50 / 94.87 · 85025 93.75 / 66.63 · 96374 642.75 / 328.23.

## Why it's not landed (the cost)

The engine computes **upcode impact = billed_99285 − negotiated_median(99283)**. The locked
seed's negotiated median for 99283 is 1450 → impact **$890** (what `demo_answer_key.json`
and `test_flags.py` assert). The real MGH median is 328.79 → impact **$2,011.21**. So
adopting real numbers **breaks 4 engine tests** and shifts the demo's per-flag dollar
figures. That's a coordinated re-tune, not a data swap:

1. `data/seed/benchmarks_v0.json` → real MGH values (run `mrf_extract.py`, below).
2. `data/seed/demo_answer_key.json` → new `expected_totals` **and** re-derived
   `seeded_flags[upcode].dollar_impact` (~$2,011) + anything downstream (dossier
   anchor/target/floor if affected).
3. `apps/api/tests/test_flags.py` + `test_dossier.py` → update the asserted impacts.
4. PRD §10.3 + §14 + README + video/deck → new spoken numbers (and Boston geography, if we
   also move Maya from Charlotte to Boston to match the MGH provenance).
5. `transform.py --check` stays the gate; keep it green after the re-tune.

All of that must move in one commit (the "change only together" rule).

## How to run the extractor (when/if approved)

```bash
python data/pipeline/mrf_extract.py \
  --mrf <path-to-MGH-standardcharges.csv> \
  --codes-from data/seed/demo_answer_key.json \
  --setting outpatient --report -o data/seed/benchmarks.json
```
Raw CSV stays local (gitignored); only the slim seed is committed. The extractor already
does payer-class segmentation (commercial-only medians), setting/modifier filters, outlier
policy, and count-weighted medians, and emits the frozen `benchmark_row` shape.

## Recommendation

Land the tool + methodology now (this PR does). **Decide separately** whether the demo
adopts real MGH numbers: if yes, it's a ~1-hour coordinated re-tune (data + answer key +
4 tests + narrative); if no, we keep the clean synthetic $1,890 demo and still tell the
"validated on real MGH data" story via the pipeline. Either way the extractor is real.
