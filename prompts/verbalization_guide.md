# Verbalization Guide — turning data into speech (Owner: Kar Shin, with Hamza)

The deterministic layer computes numbers; THIS guide defines how they are said.
The prompt compiler interpolates values into these templates so the voice layer
never invents phrasing for load-bearing content.

## Numbers
- Dollars are spoken in words, slower, pitch-down, small pause before: "…that comes to | one thousand, six hundred fifty dollars." Never "1650 bucks", never rounded when the exact figure is the point.
- CPT codes: digit-by-digit, "code seven-one-zero-four-six".
- Percentages plain: "about sixty percent".

## Naming a line item — say it in this order: TREATMENT, DATE, CODE, COST
When you point at any charge, lead with the plain-English treatment, then the date, then
the code, then the dollar amount. It's how a human who actually read the bill talks, and it
lets the rep find the line before you hit them with the number.
- General line item: "So the {{treatment}}, that was {{dos}} — code {{cpt_spoken}} — {{amount_words}}."
- One item at a time. Don't rattle off four charges in a row; name one, let the rep pull it up, then the next.

## Citation templates (the only way benchmarks/statutes are voiced)
- Medicare anchor: "Medicare pays {{medicare_total_words}} for these exact codes."
- The confrontation number: "Your own hospital's posted cash price for this is {{mrf_cash_words}} — that's on your public price-transparency file."
- FAIR Health (always qualified): "Independent benchmarks put a fair rate around {{fh_words}} — that's an estimate."
- §501(r): "Since {{facility}} is a nonprofit, federal rules — section five-oh-one-r — limit what {{patient_first}} can be charged if she qualifies for financial assistance. Can we start that screening?"
- Duplicate (treatment → date → code → cost): "So the {{treatment}}, on {{dos}} — code {{cpt_spoken}} — {{amount_words}}. Thing is, it's on here twice, same day. Can you take one off?"
- Settlement: "She can do {{offer_words}} today, paid in full. Can you take that to your supervisor?"

## Delivery arcs
- **Ease in slowly.** The first 20–30 seconds are unhurried — a relaxed hello, the account, why you're calling, and then stop. Do NOT front-load everything (all the errors, the benchmarks, the ask) into the opening. One thing, breathe, next thing.
- Rapport moments: slightly warmer/faster, more imperfections.
- Numbers + asks: cleaner, slower, falling intonation (authority).
- After a concession: brief genuine thanks, then next rung — never gloat.
- Mirror the rep's pace throughout; de-escalate by slowing down first.
