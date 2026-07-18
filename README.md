# The Negotiator

Hack-Nation 6th Global AI Hackathon — Challenge 01, powered by [ElevenLabs](https://elevenlabs.io).

Voice agents that call, compare, and haggle — pick your market, never overpay again.

## The challenge

Build an end-to-end MVP of a voice-agent system that, for a phone-priced vertical of our
choice (moving, medical bills, car buying, contractor bids, freight, equipment rental, etc.),
gathers real prices by phone, reports them in comparable form, and negotiates the best deal.

Three required modules:

1. **The Estimator** — intake by voice interview (ElevenLabs Agents) and/or document parsing,
   producing one structured job spec confirmed by the user and reused verbatim across every call.
2. **The Caller** — parallel outbound calls (real businesses, human role-play, or counter-agents)
   that describe the job consistently and extract itemised, comparable quotes.
3. **The Closer** — negotiation using leveraged competing bids and red-flag rules, plus a final
   ranked report with transcript/recording evidence and a plain-language recommendation.

Full brief: see `Challenge.pdf` in the parent folder.

## Setup

```bash
cp .env.example .env
# then fill in .env with your ElevenLabs API key (see .env.example for details)
```

## Stack

TBD.
