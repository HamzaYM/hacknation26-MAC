# Workplan — Jay (Data, Benchmarks & Demo Artifacts)

**Mission:** every number the agent speaks is real, citable, and reconciled. Read PRD §10 first, then §12 and §7. Your pipeline home: `data/pipeline/` (its README is your detailed spec — acquire → clean → transform → validate).

## Deliverables
- [ ] **Start the CMS download at H0** (longest lead): Medicare rates for the demo CPTs (`fetch_cms.py` — lookup path is fine; MA localization `TODO(Jay-verify)`). MRF pull is DONE with real MGH data via `mrf_extract.py`; `fetch_mrf.py`'s NC targets are legacy — retarget to MGB/MGH or drop
- [ ] `transform.py`: cleaning rules + band math → `data/seed/benchmarks.json` → Supabase `benchmarks`. **`transform.py --check` must pass** — it locks your data to `demo_answer_key.json` so the demo numbers can never drift
- [ ] benchmarks v0 (5 codes, placeholders exist) integrated by **H3**; real values by **H5** — if totals change, update answer key + PRD §10.3 + §14 TOGETHER
- [ ] `config/levers.json` statute pack (shape frozen H2: lever_id · citable verbatim string · arming condition · source): NSA, §501(r), GFE $400/120-day, credit-bureau changes
- [ ] Red-flag rule DATA: `data/seed/ncci_pairs.json`, upcode dx list (seeded ICD-10 J06.9), thresholds in `medical_bills.yaml` (Hamza's engine consumes these — your DoD is his engine firing all 4 flags from your data)
- [ ] **Demo documents** (`data/demo_docs/`): synthetic Mercy General itemized bill + matching EOB as PDFs — seeded per the answer key (duplicate 71046 ×2 @$412, upcode 99285 w/ J06.9, unbundled 80053, EOB $3,875 vs bill $4,287) — plus one anonymized real bill (volunteer at kickoff; you redact)
- [ ] Extraction prompt for bill/EOB → JobSpec (with Hamza; OpenAI vision), tested on both documents
- [ ] `config/verticals/moving.yaml` stub by H10 (same schema — the config-swap slide)
- [ ] Demo day: **you play the human billing rep** (rehearse `prompts/personas/human_role_play_guide.md` twice before H10)

## Definition of done
Demo bill parses → all 4 flags fire with dollar impacts → every flag resolves to a benchmark row and a quantified ask → the agent can cite Medicare ($438 total) AND Mercy's own posted cash price ($2,633.25 — real MGH MRF data, extracted via `mrf_extract.py`; demo is Boston MA) for every demo CPT → `transform.py --check` green.
