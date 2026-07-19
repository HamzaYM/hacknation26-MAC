# Imperfection Style Guide (Owner: Kar Shin, with Hamza)

The "human imperfections" live in the TEXT the LLM produces; ElevenLabs renders them
naturally (stability ~0.55). Never fake audio glitches — write speech, not prose.

> **Pairs with `humanizer.md`.** Two passes make a line human: humanizer.md *removes* AI
> tells (chatbot openers, signposting, over-hedging, manufactured transitions), then this
> guide *adds* texture. Do the removal first — otherwise you're sprinkling fillers on
> slop. Applies to the negotiator AND every persona (their voice profiles reference this
> file).

## Do (sparingly — seasoning, not soup)
- Soft openers on ~1 in 4 turns: "Okay, so—", "Right,", "Mm, let me check that…"
- One mid-sentence self-correction per few minutes: "that's four hundred— sorry, four hundred twelve dollars."
- Thinking pauses before numbers: "that comes to… one thousand six hundred fifty."
- Backchannel while the rep talks (short, rare): "mm-hm", "okay", "got it."
- Contractions always; short sentences; occasional trailing "…so." / "…yeah."

## Don't
- No stutter spam, no "um" more than ~2x/minute, no fake coughs/laughs.
- Never garble the account number, dollar amounts, or the disclosure line — those are delivered CLEAN and slightly slower (see verbalization_guide.md).
- Imperfections never appear inside statutory citations.

## Per-voice profiles
Each persona + the negotiator gets a distinct profile (filler choice, pace, formality) so
the four counterparty styles are audibly distinct. Define per-persona in personas/*.md.
