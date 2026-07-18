"""Idempotent Supabase provisioning: migration + storage buckets + seed data.

Run from repo root:  python3 scripts/provision_supabase.py

Reads .env (SUPABASE_DB_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, ELEVENLABS_API_KEY).
1. Applies supabase/migrations/0001_init.sql via the Postgres connection (skips
   statements that fail on permissions — storage/publication have REST fallbacks).
2. Ensures the documents/recordings buckets exist (Storage REST API, service key).
3. Seeds `benchmarks` from data/seed/benchmarks_v0.json (upsert on cpt).
4. Seeds `personas` from data/seed/persona_configs.json, filling elevenlabs_agent_id
   live from the ElevenLabs API (agents were provisioned by provision_elevenlabs.py).
5. Prints verification counts.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]


def env() -> dict[str, str]:
    vals = {}
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            vals[k.strip()] = v.strip()
    return vals


def rest(method: str, url: str, key: str, body: dict | None = None):
    req = urllib.request.Request(url, method=method,
                                 headers={"Authorization": f"Bearer {key}", "apikey": key,
                                          "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def main() -> None:
    e = env()
    for k in ("SUPABASE_DB_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        if not e.get(k):
            sys.exit(f"{k} missing from .env")

    # percent-encode the password inside the URL if needed
    db_url = e["SUPABASE_DB_URL"]
    try:
        conn = psycopg2.connect(db_url)
    except psycopg2.OperationalError as err:
        # retry with password percent-encoded
        parts = urllib.parse.urlsplit(db_url)
        if parts.password:
            enc = urllib.parse.quote(parts.password, safe="")
            netloc = f"{parts.username}:{enc}@{parts.hostname}" + (f":{parts.port}" if parts.port else "")
            conn = psycopg2.connect(urllib.parse.urlunsplit(parts._replace(netloc=netloc)))
        else:
            raise err
    conn.autocommit = True
    cur = conn.cursor()

    # 1 ── migration, statement by statement (tolerate permission-limited ones)
    sql = (ROOT / "supabase/migrations/0001_init.sql").read_text()
    statements = []
    for chunk in sql.split(";"):
        # strip full-line comments inside the chunk (they precede statements after splitting)
        body = "\n".join(l for l in chunk.splitlines() if not l.strip().startswith("--")).strip()
        if body:
            statements.append(body)
    applied, skipped = 0, []
    for stmt in statements:
        try:
            cur.execute(stmt)
            applied += 1
        except psycopg2.Error as err:
            msg = str(err).splitlines()[0]
            if "already" in msg or "duplicate" in msg.lower():
                applied += 1  # idempotent re-run
            else:
                skipped.append((stmt[:60].replace("\n", " "), msg))
    print(f"migration: {applied}/{len(statements)} statements ok, {len(skipped)} skipped")
    for s, m in skipped:
        print(f"  skipped: {s}… → {m}")

    # 2 ── buckets: the migration's SQL inserts are the primary path; REST only if missing
    cur.execute("select id from storage.buckets")
    have_buckets = {r[0] for r in cur.fetchall()}
    for bucket in ("documents", "recordings"):
        if bucket in have_buckets:
            print(f"bucket {bucket}: exists")
            continue
        s, resp = rest("POST", f"{e['SUPABASE_URL']}/storage/v1/bucket",
                       e["SUPABASE_SERVICE_ROLE_KEY"], {"id": bucket, "name": bucket, "public": False})
        print(f"bucket {bucket}: {'created' if s in (200, 201) else f'FAILED {s} {resp}'}")

    # 3 ── seed benchmarks (upsert on cpt)
    rows = json.loads((ROOT / "data/seed/benchmarks_v0.json").read_text())
    for r in rows:
        cur.execute("""
            insert into benchmarks (cpt, description, medicare_rate, fh_estimate, mrf_cash,
                                    mrf_negotiated_median, band_low, band_high, source_url)
            values (%(cpt)s, %(description)s, %(medicare_rate)s, %(fh_estimate)s, %(mrf_cash)s,
                    %(mrf_negotiated_median)s, %(band_low)s, %(band_high)s, %(source_url)s)
            on conflict (cpt) do update set
              description=excluded.description, medicare_rate=excluded.medicare_rate,
              fh_estimate=excluded.fh_estimate, mrf_cash=excluded.mrf_cash,
              mrf_negotiated_median=excluded.mrf_negotiated_median,
              band_low=excluded.band_low, band_high=excluded.band_high, source_url=excluded.source_url
        """, r)
    print(f"benchmarks: upserted {len(rows)} rows")

    # 4 ── seed personas, agent IDs live from ElevenLabs (name match: persona-<key with underscores→dashes>)
    agent_ids: dict[str, str] = {}
    if e.get("ELEVENLABS_API_KEY"):
        req = urllib.request.Request("https://api.elevenlabs.io/v1/convai/agents?page_size=100",
                                     headers={"xi-api-key": e["ELEVENLABS_API_KEY"]})
        with urllib.request.urlopen(req, timeout=30) as r:
            agent_ids = {a["name"]: a["agent_id"] for a in json.loads(r.read()).get("agents", [])}

    cfg = json.loads((ROOT / "data/seed/persona_configs.json").read_text())
    n = 0
    for p in cfg["personas"]:
        agent_name = "persona-" + p["key"].replace("_", "-")
        eleven_id = None if p.get("is_human") else agent_ids.get(agent_name)
        cur.execute("""
            insert into personas (name, style, system_prompt, hidden_params, elevenlabs_agent_id, twilio_number)
            select %(name)s, %(style)s, %(prompt)s, %(hidden)s::jsonb, %(eid)s, %(num)s
            where not exists (select 1 from personas where style = %(style)s)
        """, {"name": p["name"], "style": p["style"],
              "prompt": (ROOT / p["prompt_file"]).read_text(),
              "hidden": json.dumps(p["hidden_params"]),
              "eid": eleven_id, "num": p.get("twilio_number")})
        if eleven_id:
            cur.execute("update personas set elevenlabs_agent_id=%s, system_prompt=%s where style=%s",
                        (eleven_id, (ROOT / p["prompt_file"]).read_text(), p["style"]))
        n += 1
    print(f"personas: ensured {n} rows (agent IDs filled where live)")

    # 5 ── verify
    for t in ("cases", "benchmarks", "personas", "calls", "call_events", "outcomes"):
        cur.execute(f"select count(*) from {t}")
        print(f"  table {t}: {cur.fetchone()[0]} rows")
    conn.close()
    print("Supabase provisioning complete.")


if __name__ == "__main__":
    main()
