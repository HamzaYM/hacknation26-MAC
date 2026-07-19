# DECISION (Hamza, 2026-07-18): Real MGH numbers adopted · demo relocated to Boston MA

**For J — start immediately; don't wait for the re-tune PR.** (A coordinated PR updating
PRD §3/§10.1/§10.3/§14, both benchmark seeds, the answer key, 4 test asserts, persona
configs, and regenerated demo PDFs is in flight and lands shortly. This memo is the
decision + numbers so you can move now.)

## Decided
1. **Adopt real MGH price-transparency figures** (your proposal — approved). Cash + commercial
   negotiated medians from `042697983_Massachusetts-General-Hospital_StandardCharges.csv`.
2. **Demo moves to Boston, MA** (Maya, insurer = Blue Cross Blue Shield of Massachusetts,
   ER group renamed "Bay State Emergency Physicians").
3. **Facility name stays FICTIONAL** — "Mercy General Hospital, Boston." MGH is named only as
   the *data source* ("benchmarks derived from a real Boston hospital's published price file").
   Never present the counterparty as MGH itself.

## Authoritative numbers (locked; the in-flight PR encodes these)
| CPT | Medicare (unchanged, synthetic) | MGH cash (real) | MGH neg. median (real) |
|---|---|---|---|
| 99283 | 245.00 | 1409.25 | 328.79 |
| 71046 | 63.00 | 354.00 | 180.78 |
| 80053 | 14.50 | 133.50 | 94.87 |
| 85025 | 10.80 | 93.75 | 66.63 |
| 96374 | 104.70 | 642.75 | 328.23 |
| **Totals** | **438.00** | **2633.25** | **999.30** |

Upcode impact becomes **$2,011.21** (2340 − 328.79). Arc endpoints UNCHANGED:
4287 → 3875 → 2400 → **1650 (−62%)**; anchor 657 / target 876 / floor 1700; human-rep floor 1500.
New talking point: commercial insurers pay *below* the cash price here ($999.30 vs $2,633.25).

## J's next moves (in priority order)
1. **Real MA Medicare rates** — the one still-synthetic column. Pull MA-locality PFS/OPPS/CLFS
   for the 5 codes (your `pfs_lookup.csv` path is fine); if the $438 total shifts, that's a
   second coordinated re-tune — bring the numbers to Hamza/Claude first, don't push directly.
2. **Retarget `fetch_mrf.py` TARGETS** from the legacy NC entries (Atrium/Novant Charlotte) to
   MGH/Mass General Brigham (you have the file + `mrf_extract.py` already proven on it).
3. The demo PDFs regenerate in the in-flight PR (Boston address, BCBS-MA, Bay State ER group) —
   nothing for you there unless you want to restyle them.
