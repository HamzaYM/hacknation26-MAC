# Verbalization Guide — turning data into speech (Owner: Kar Shin, with Hamza)

The deterministic layer computes numbers; THIS guide defines how they are said.
The prompt compiler interpolates values into these templates so the voice layer
never invents phrasing for load-bearing content.

## Numbers
- Dollars are spoken in words, slower, pitch-down, small pause before: "…that comes to | one thousand, six hundred fifty dollars." Never "1650 bucks", never rounded when the exact figure is the point.
- CPT codes: digit-by-digit, "code seven-one-zero-four-six".
- Percentages plain: "about sixty percent".

## Citation templates (the only way benchmarks/statutes are voiced)
- Medicare anchor: "Medicare pays {{medicare_total_words}} for these exact codes."
- The confrontation number: "Your own hospital's posted cash price for this is {{mrf_cash_words}} — that's on your public price-transparency file."
- FAIR Health (always qualified): "Independent benchmarks put a fair rate around {{fh_words}} — that's an estimate."
- §501(r): "Since {{facility}} is a nonprofit, federal rules — section five-oh-one-r — limit what {{patient_first}} can be charged if she qualifies for financial assistance. Can we start that screening?"
- Duplicate: "Code {{cpt_spoken}} appears twice on {{dos}} — {{amount_words}} each time. Can you remove the duplicate?"
- Settlement: "She can pay {{offer_words}} today, settled as paid in full. Can you take that to your supervisor?"

## Delivery arcs
- Rapport moments: slightly warmer/faster, more imperfections.
- Numbers + asks: cleaner, slower, falling intonation (authority).
- After a concession: brief genuine thanks, then next rung — never gloat.
- Mirror the rep's pace throughout; de-escalate by slowing down first.
