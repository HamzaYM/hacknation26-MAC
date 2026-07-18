# Using Claude Code subscriptions API-style (cost saver) — verified 2026-07

**TL;DR:** headless `claude -p` runs on Pro/Max subscription OAuth (no API key) and can return
schema-validated JSON. Use it for offline TEXT tasks. Do NOT use the Agent SDK on subscription
auth (API-key only; ToS forbids powering app features with claude.ai login). Vision parsing of
bills/EOBs → OpenAI credits (headless vision is underdocumented; don't risk demo time).

## Routing table
| Task | Runs on |
|---|---|
| Live call turns | ElevenLabs-billed brain LLM (no key at all) |
| Bill/EOB vision parsing | OpenAI API (gpt-5.6-terra default) |
| Report narrative, dossier prose, persona drafts | `claude -p` on subscription |
| Structured JSON from Claude | `claude -p --output-format json --json-schema '…'` |

## Commands
```bash
# plain text
claude -p "Draft the plain-language recommendation for this outcome: …"

# schema-validated JSON (validated result lands in the structured_output field)
claude -p "Extract the key claims" \
  --output-format json \
  --json-schema '{"type":"object","properties":{"claims":{"type":"array","items":{"type":"string"}}}}'

# from FastAPI
import subprocess, json
r = subprocess.run(["claude", "-p", prompt, "--output-format", "json",
                    "--json-schema", schema_json], capture_output=True, text=True)
out = json.loads(r.stdout)
```

## Gotchas
- Don't pass `--bare` — it skips subscription OAuth and demands an API key.
- ~2–5s CLI startup per call; serial. Fine for offline generation, never for live turns.
- Non-interactive usage draws from a capped monthly quota on the subscription — monitor it.
- Each teammate's machine must have run `/login` once (subscription OAuth cached).
