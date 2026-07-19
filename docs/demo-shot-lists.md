# Demo Shot Lists — 2 × 60s Submission Videos

> For **Kar Shin** (director) and **Hamza**. Replaces the 3:30 single-video plan in `docs/video-script.md`.
> Every number below reconciles with `data/seed/demo_answer_key.json` — the single source of demo truth.
> Every shot shows something **real and built today** (exceptions are marked `[PENDING]` with a fallback).

## Numbers card (say these, never variants)

| Value | Say / show |
|---|---|
| Total billed | $8,432 |
| Patient balance | $4,287 |
| EOB responsibility | $3,875 |
| The 4 flags | duplicate 71046 **$412** · upcode 99285→99283 **$2,011.21** · unbundle 80053 **$642** · EOB mismatch **$412** |
| Benchmarks | Medicare total **$438** · hospital posted cash **$2,633.25** · negotiated median **$999.30** |
| Supervisor arc | $4,287 → $3,875 → $2,400 → **$1,650 settled** (ref MG-ADJ-2247) |
| Reduction | say **"−62%"** (exact: 61.5%) |
| Collections arc | $980 → **$392** paid-in-full (ref MRS-55217) |
| Charity arc | application initiated, ref **BSEP-FA-1102** |
| Floor / target / anchor | $1,700 / $876 / $657 — $1,650 is *below* floor, so the engine forces a human approval (`escalation_required`) |
| Voice-interview beat | "What could you comfortably pay today?" → "Maybe seventeen hundred" ($1,700 lump sum) |

## The 7 success criteria (from Challenge.pdf) — coverage map

| # | Criterion (short) | Proven in |
|---|---|---|
| S1 | Loop closed: intake → calls → negotiation → ranked recommendation w/ transcript evidence | A1–A6 (whole arc), A6 |
| S2 | One job spec, by voice interview + ≥1 document, user-confirmed, reused verbatim on every call | A2, A3, B2 |
| S3 | Live calls vs ≥3 distinct negotiation styles; every quote structured, fees itemised | A4, B3, B4 |
| S4 | Price/terms measurably change mid-call from gathered leverage, not script | A5, B2, B5 |
| S5 | AI disclosure + honesty constraints hold; friction/hang-ups/"are you a robot?" handled | A4, B2, B6 |
| S6 | Every call ends in a structured outcome (quote / callback / documented decline) | A4, A5 |
| S7 | Report ranks all quotes, cites recordings + transcripts, plain-language recommendation | A6 |

All 7 hit across the two videos. Strong-submission hints also on camera: real market data (B5), golden-call evals (B6), config-not-code (B7), real telephony (B3).

---

## VIDEO A — UI/UX (60s, the product loop as Maya)

Record everything on the **public app: https://hagglfor.me** (URL visible in the address bar — it is real and live). Log in on camera with the demo Supabase account.

| Time | Shot (real, on camera) | VO / audio | Proves |
|---|---|---|---|
| **A1** 0:00–0:05 | The real bill PDF (`data/demo_docs/mercy_general_bill.pdf`), $4,287 balance circled/zoomed. | "Maya has insurance. She still owes $4,287 for one ER visit. Our AI advocate picks up the phone." | Hook / S1 setup |
| **A2** 0:05–0:14 | `/intake` on hagglfor.me: drag the bill PDF into the upload card → **live vision parse**: "23 line items extracted", pill "Matches your case records". Quick cut: the embedded ElevenLabs voice widget mid-question — PLAY REAL AUDIO: "What could you comfortably pay today?" / "Maybe seventeen hundred." | "Upload the bill and EOB, and a voice interview asks only what documents can't answer. Both build one job spec." | **S2** (voice + document intake) |
| **A3** 0:14–0:22 | `/confirm` — "Here's the plan — confirm before we dial": 4 flags with dollar impacts ($412 / $2,011.21 / $642 / $412), 3 entity chips, click **"Looks right — make the calls"**. | "Four billing errors found, each with a dollar impact. Nothing dials until Maya approves — and this exact spec goes into every call." | **S2** (confirm + verbatim reuse) |
| **A4** 0:22–0:38 | War Room, 3 calls, 3 styles (fast cuts between call views, or the multi-call view if gap G4 lands): ① Stonewaller hangs up → **"documented decline · callback scheduled"** outcome card. ② Policy-citer — PLAY AUDIO: "Am I talking to a robot?" / "You are — I'm an AI advocate authorized by Maya…" → badge "AI advocate has disclosed" → charity app initiated, **ref BSEP-FA-1102**. ③ Collections ticker **$980 → $392**, ref MRS-55217. | "Three calls, three different negotiators. It discloses it's an AI, survives a hang-up — that's a documented outcome, not a failure." | **S3, S5, S6** |
| **A5** 0:38–0:51 | The supervisor call: ticker **$4,287 → $3,875 → $2,400 → $1,650**, lever chips arming *before* each drop; PLAY AUDIO of the duplicate cite ("code 71046 appears twice…"); flash the `escalation_required` event at $1,650. | "Duplicate X-ray removed. Medicare and the hospital's own posted cash price cited. $4,287 becomes $1,650 — sixty-two percent off — and because $1,650 beat the floor, a human signs off on the final number." | **S4** (+S6) |
| **A6** 0:51–1:00 | `/report`: ranked outcomes with ref#s and rep names, billed vs fair-band vs achieved table, expand **Evidence** → cited transcript lines + the call-recording audio player, plain-language recommendation. | "Every call ends structured. Ranked, cited, explained in plain English. Haggl." | **S7, S1** (loop closed) |

Director notes (A): A2 parse is live against the real API — rehearse once, it takes ~10s real time, so start the upload before the shot's in-point. A4: today the War Room is one call per view (`?call_id=`); use three pre-opened tabs unless G4 (multi-call view) merges. A6: audio player appears only when a recording exists — depends on G2.

---

## VIDEO B — TECH (60s, for judges/engineers: code, terminals, dashboards)

| Time | Shot (real, on camera) | VO / audio | Proves |
|---|---|---|---|
| **B1** 0:00–0:07 | PRD §6 architecture diagram (Next.js ↔ FastAPI ↔ Supabase Realtime ↔ ElevenLabs Agents ↔ Twilio PSTN). | "The LLM is the mouth, not the brain. Negotiation policy is a deterministic server-side state machine." | Framing for S4/S5 |
| **B2** 0:07–0:17 | Split screen: `prompts/negotiator_system.md` rule "only figures returned by get_benchmark" beside a live terminal — `curl POST /tools/report_lever_result` with `"stonewalled"` → JSON forces `reach_authority`; second curl offering above the floor → rejected. | "Mid-call the agent asks the server what to do next. It can't invent a number and it can't overpay — the tools won't let it." | **S5** honesty + **S4** mechanism (+S2: `get_case_brief` serves the confirmed spec verbatim) |
| **B3** 0:17–0:27 | Terminal: `python3 scripts/place_test_call.py` → a real phone on camera rings on **+1 857 675 7033** (Stonewaller line; negotiator dials out from +1 857 578 2966) → ElevenLabs dashboard shows the live conversation. `[PENDING a2a re-test — deadlock fix deployed; fallback: dashboard call log of the connected PSTN call + a live browser-session call with Kar Shin role-playing]` | "These aren't sound effects. Two ElevenLabs agents on a real Twilio call — same code path a real hospital call would ride." | **S3** (live calls, real telephony) |
| **B4** 0:27–0:36 | ElevenLabs dashboard: the 6 provisioned agents (negotiator, intake, 4 personas). Then War Room beside the Supabase `call_events` table streaming rows during a launched call. | "Four counterparty personas with hidden concession functions the negotiator can't see. Every event streams over Supabase Realtime — nothing on screen is scripted markup." | **S3** (+S6: structured `call_outcome` rows) |
| **B5** 0:36–0:45 | `data/pipeline/`: the real MGH price-transparency extract (CMS v3.0.0, 159k rows → slim extract); `python transform.py --check` passing; cash **$2,633.25** / negotiated median **$999.30** / Medicare **$438**. | "Benchmarks come from a real Boston hospital's published price file, gated by a reconciliation check against the demo answer key." | **S4** (leverage grounded in real market data) |
| **B6** 0:45–0:53 | `python scripts/eval_call.py <call>.json` → deterministic pass table: disclosure early ✓ · every spoken number citable ✓ · structured outcome ✓ · price move traceable to a lever ✓. | "Every call is audited — disclosure, honesty, structure. A pass/fail gate, not a vibe." | **S5** (+golden-calls hint) |
| **B7** 0:53–1:00 | `config/verticals/medical_bills.yaml` beside `moving.yaml`, ladder/flags diff highlighted. End card: **hagglfor.me**. | "The whole vertical is one YAML file. Swap it and the same engine haggles moving quotes. Try it — it's live." | Config-not-code hint |

Director notes (B): B2 curls are real endpoints (47+ passing tests behind them) — pre-write the two curl commands in shell history. B3 is the only conditional shot in either video; shoot the fallback regardless so the edit has both. B5: run `--check` live; it's fast.

---

## Remaining top gaps (post-audit, still true today) — ranked

Audit items now **obsolete** (done since the audit): intake voice widget + live PDF vision parse (audit #3 — built, verified with exact reconciliation and all 4 flags on real PDFs), report transcript-evidence + audio slots (audit #4), Supabase login, public deployment at hagglfor.me.

| Rank | Gap (audit ref) | Why it matters | Owner | Effort |
|---|---|---|---|---|
| **G1** | One **verified real unscripted call** end-to-end: re-run the PSTN agent-to-agent test (deadlock fix deployed, negotiator now opens with the disclosure) or a human role-play call over the real number (audit #1) | Flips the demo from "staged screenplay" — the brief's explicit weak-submission trap — to "price moved on a real call". Gates shot B3. | Hamza (place/verify) + Kar Shin (role-play fallback) + Claude (debug) | 30–60 min if the fix holds |
| **G2** | **Real call audio** captured and playable: fetch `GET /v1/convai/conversations/{id}/audio` → recordings bucket (`webhooks._store_recording` already written) → report + War Room (audit #2) | "Play the calls in your demo" is a hard requirement. Slots are built; zero audio files exist. Gates A2/A4/A5 audio and the A6 player. | Claude (wiring) + Hamza (run) | ~1 h |
| **G3** | **Compute the honesty audit** instead of asserting it: reuse `scripts/eval_call.py` allowed-numbers logic as a post-call step writing a real `honesty_audit` event (audit #5) | Converts C3/S5 from claimed to verified — the "honest about the hard parts" differentiator. Logic already exists. | Claude | ~1 h |
| **G4** | **Multi-call War Room**: subscribe by `case_id`, render 3 concurrent call cards (audit #6) | Makes "parallel quote gathering" + "3 styles" visible in ONE shot (A4). Today: one call per `?call_id=` view; the 3-tab fallback works but is weaker. | Claude (build) + Susy (design sign-off) | 1–2 h |
| **G5** | **Locked-numbers sweep, remainder** (audit #7): `apps/web/app/bills/[caseId]/page.tsx:248` still says cash price "$1,890" (locked: $2,633.25) and `:283` "Carolina Emergency Physicians"; also `apps/web/app/action-items/page.tsx` and `apps/web/lib/procedures.ts` (should be "Bay State Emergency Physicians"). Bills-list Boston fix already landed. | Judges who diff the report against the call WILL catch drift. | Claude | ~20 min |
| **G6** | **Config-swap proof on camera** (audit #8): `moving.yaml` exists; wire a `VERTICAL` env read (config loader already parameterized) or at minimum film the yaml diff (shot B7) | Hits the brief's explicit "swap a config file, not rewrite your agents" line. | Claude (env wire) + Kar Shin (film) | ~30 min |

---

## Judge Q&A cheat sheet (hardest questions, honest answers)

1. **"Are these real phone calls?"** Real infrastructure end-to-end — ElevenLabs agents, real Twilio numbers, a real PSTN ring — but the far end is our counterparty agents plus one human role-play. The brief explicitly allows all three setups; everything downstream of the dial tone is production-shaped.
2. **"Why not call a real hospital?"** We hold no real active bill; calling a hospital about a fake account is impossible and unethical. We chose counter-agents + role-play deliberately, not as a shortcut.
3. **"Isn't the negotiation scripted?"** The montage calls are replays driven through the real state machine. The live call is unscripted: personas have hidden concession functions the negotiator can't see — the price moves only when a cited lever unlocks a concession.
4. **"Where do the benchmarks come from?"** A real Boston hospital's published CMS price-transparency file (159k rows, filtered locally): cash $2,633.25, negotiated median $999.30 for the demo codes. Medicare total $438 is synthetic-locked pending MA-locality verification, and labeled as such.
5. **"Is Mercy General real?"** No — fictional facility, fictional patient (Maya Chen), PDFs generated from our fixtures. The real hospital is only the *data source* for benchmarks, never the negotiation counterparty.
6. **"Does it disclose it's an AI?"** First utterance of every call, hard rule to never deny it, and "am I talking to a robot?" is handled on camera in the policy-citer call.
7. **"How do you stop the model inventing numbers or facts?"** Tool-gating: the only citable price source is `get_benchmark`; the prompt forbids uncited figures and invented case facts; the server state machine enforces floor/target, so it can't overpay either.
8. **"How is honesty verified, not just claimed?"** `eval_call.py` deterministically diffs every spoken number against the allowed set (disclosure timing + structured ending too). Honest caveat: in the simulated calls the in-UI audit badge is asserted; the computed post-call audit is G3 on our list.
9. **"What breaks when you change verticals?"** One YAML file: flags, ladder, escalation triggers, voice. `moving.yaml` sits beside `medical_bills.yaml` with the same schema; the engine loads either.
10. **"Why trust the −62%?"** Every step is traceable: $4,287 → $3,875 (duplicate 71046, $412) → $2,400 (Medicare $438 + posted cash $2,633.25 cited) → $1,650 settled, ref MG-ADJ-2247 — and because $1,650 is below the $1,700 floor, the engine forced a human approval before accepting.
