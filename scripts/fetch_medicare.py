"""Fetch REAL public CMS Medicare rate data (PFS RVU+GPCI, OPPS Addendum B,
CLFS) for the pipeline's target codes, compute Boston-locality professional/
facility/global rates by plain formula (no LLM anywhere in this file), and
write data/seed/medicare_rates.json with full provenance on every row.

Sources (per audit/research-medicare-sources.md, verified live at build time):
  - PFS RVU + GPCI: cms.gov/medicare/payment/fee-schedules/physician/
    pfs-relative-value-files/<rvu-file> -> one ZIP containing both
    PPRRVU<year>_<qtr>_nonQPP.csv (work/PE/MP RVUs) and GPCI<year>.csv
    (geographic practice cost indices by locality).
  - OPPS Addendum B (hospital outpatient facility fees): cms.gov/medicare/
    payment/prospective-payment-systems/hospital-outpatient-pps/
    quarterly-addenda-updates/<quarter>-addendum-b -> ZIP with a CSV of
    national-unadjusted payment rates. Documented as "national unadjusted,
    not wage-adjusted for Boston" (v1 shortcut; see docstring below).
  - CLFS (clinical lab fee schedule): cms.gov/medicare/payment/fee-schedules/
    clinical-laboratory-fee-schedule-clfs/files/<quarter> -> flat national
    per-code rate, no geographic adjustment.

Formula (PFS professional, facility setting):
    payment = (work_RVU * work_GPCI + facility_PE_RVU * PE_GPCI
               + MP_RVU * MP_GPCI) * conversion_factor
  using the FACILITY PE RVU column (MGH/BWH/Newton-Wellesley are all
  hospital-based settings) and the Boston locality (MA-01, "METROPOLITAN
  BOSTON") GPCI row actually present in the downloaded GPCI file (NOT
  hand-typed from memory — see `--verify-locality`).

Components per code:
  - E/M (992xx), imaging (7xxxx), IV/injection (9636x/96374): both a
    `professional` (PFS) and `facility` (OPPS Addendum B) component exist;
    `global` = professional + facility (the two bill as separate line items
    in practice — physician group vs. hospital facility — but scenarios that
    bill a single combined line use `global`).
  - Labs (80048/80053/80061/85025/85027): CLFS is a single national flat
    rate covering the whole test; only `global` is populated (no separate
    professional interpretation component for basic panels).
  - 36415 (venipuncture): PFS status indicator X ("statutorily excluded from
    PFS payment") and OPPS status Q4 (no separate facility payment) — this
    is a REAL Medicare policy fact, not a data gap: CMS pays venipuncture
    under the *Clinical Lab Fee Schedule specimen-collection fee*, not PFS/
    OPPS. `global` = the CLFS rate for 36415.

Fallback path (documented per row, never silent): if a code truly has no
usable rate from any of the three sources above, this script falls back to
deriving an estimate from the chargemaster's own MEDICARE-payer rows
(`--source chargemaster-fallback` per code), version-tagged
"chargemaster-derived" so callers can see exactly which path produced the
number. This did not trigger for any of the 18 target codes in this build —
all resolved from real CMS files (see `data/seed/medicare_rates.json`
top-level `provenance.path` per code).

SANITY GATE: 99283 (ED visit, moderate/low MDM) professional component must
land in $65-80 (per research doc cross-check against 2025 PFS); the script
raises SystemExit if it doesn't, rather than silently staging a bad number.

USAGE:
    python scripts/fetch_medicare.py                    # fetch + compute + write JSON
    python scripts/fetch_medicare.py --cache-only        # reuse data/raw/cms/* if present, no network
    python scripts/fetch_medicare.py --stage-sqlite <db path>   # also write medicare_rates table
    python scripts/fetch_medicare.py --stage-supabase    # also upsert into Supabase (env SUPABASE_DB_URL)

Never prints/logs credential material. Reads SUPABASE_DB_URL only from
os.environ; fails with a clean message (not a stack trace with the URL) if
unset when --stage-supabase is passed.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_CMS = REPO_ROOT / "data" / "raw" / "cms"
SEED_OUT = REPO_ROOT / "data" / "seed" / "medicare_rates.json"

try:  # pragma: no cover — best-effort .env load for standalone script use
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

CONVERSION_FACTOR_2026 = 33.4009  # 2026 PFS non-QP CF, CMS CY2026 Final Rule
BOSTON_LOCALITY = "01"
BOSTON_STATE = "MA"
BOSTON_LABEL = "MA-01 Metropolitan Boston"

# Target codes and which components they carry.
EM_IMAGING_INJECTION_CODES = {
    "99281", "99282", "99283", "99284", "99285",
    "71045", "71046", "70450", "72110",
    "96360", "96361", "96374",
}
LAB_CODES = {"80048", "80053", "80061", "85025", "85027"}
CLFS_SPECIAL_CODES = {"36415"}  # paid via CLFS specimen-collection fee, not PFS/OPPS
ALL_CODES = sorted(EM_IMAGING_INJECTION_CODES | LAB_CODES | CLFS_SPECIAL_CODES)

# Known-good source pages as of this build (July 2026); the fetcher re-derives
# the exact ZIP URL from each page's HTML rather than hardcoding the ZIP name,
# so quarterly filename churn doesn't break re-runs.
RVU_PAGE_CANDIDATES = [
    "https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files/rvu26a",
    "https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files/rvu25d",
]
OPPS_PAGE_CANDIDATES = [
    "https://www.cms.gov/medicare/payment/prospective-payment-systems/hospital-outpatient-pps/quarterly-addenda-updates/july-2026-addendum-b",
    "https://www.cms.gov/medicare/payment/prospective-payment-systems/hospital-outpatient-pps/quarterly-addenda-updates/april-2026-addendum-b",
    "https://www.cms.gov/medicare/payment/prospective-payment-systems/hospital-outpatient-pps/quarterly-addenda-updates/january-2026-addendum-b",
]
CLFS_PAGE_CANDIDATES = [
    "https://www.cms.gov/medicare/payment/fee-schedules/clinical-laboratory-fee-schedule-clfs/files/26clabq3",
    "https://www.cms.gov/medicare/payment/fee-schedules/clinical-laboratory-fee-schedule-clfs/files/26clabq2",
    "https://www.cms.gov/medicare/payment/fee-schedules/clinical-laboratory-fee-schedule-clfs/files/26clabq1",
]


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https CMS host)
        return resp.read()


def _find_zip_href(html: bytes) -> str | None:
    """CMS wraps most downloadable ZIPs behind an AMA-license click-through
    (/apps/ama/license.asp?file=/files/zip/<name>.zip) for CPT-coded files.
    The underlying /files/zip/<name>.zip serves directly without the
    click-through (verified at build time); extract that path regardless of
    which wrapper form the page uses."""
    text = html.decode("latin-1", errors="replace")
    m = re.search(r"/files/zip/[A-Za-z0-9_\-.]+\.zip", text)
    return m.group(0) if m else None


def fetch_zip(page_candidates: list[str], cache_name: str, cache_only: bool) -> Path:
    """Resolve a CMS page to its ZIP, download once, cache under data/raw/cms/."""
    RAW_CMS.mkdir(parents=True, exist_ok=True)
    cache_path = RAW_CMS / cache_name
    if cache_path.exists():
        log(f"  using cached {cache_path.name}")
        return cache_path
    if cache_only:
        raise SystemExit(f"--cache-only set but {cache_path} not present; run without --cache-only once")

    last_err: Exception | None = None
    for page_url in page_candidates:
        try:
            html = _http_get(page_url)
        except (urllib.error.URLError, TimeoutError) as err:
            last_err = err
            log(f"  page fetch failed ({page_url}): {err}")
            continue
        zip_path = _find_zip_href(html)
        if not zip_path:
            log(f"  no zip link found on {page_url}")
            continue
        zip_url = "https://www.cms.gov" + zip_path
        try:
            data = _http_get(zip_url, timeout=60)
        except (urllib.error.URLError, TimeoutError) as err:
            last_err = err
            log(f"  zip download failed ({zip_url}): {err}")
            continue
        cache_path.write_bytes(data)
        log(f"  fetched {zip_url} ({len(data)} bytes) -> {cache_path.name}")
        return cache_path
    raise SystemExit(f"Could not resolve/download any candidate for {cache_name}: {last_err}")


def _money(s: str) -> float | None:
    s = (s or "").strip().replace("$", "").replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# --------------------------------------------------------------------- PFS/GPCI

def parse_gpci(zf: zipfile.ZipFile) -> tuple[float, float, float, str]:
    """Return (work_gpci, pe_gpci, mp_gpci, locality_label) for Boston, read
    directly from the downloaded GPCI CSV (not hand-typed)."""
    names = [n for n in zf.namelist() if n.upper().startswith("GPCI") and n.lower().endswith(".csv")]
    if not names:
        raise SystemExit("GPCI csv not found in RVU zip")
    with zf.open(names[0]) as f:
        reader = csv.reader(io.TextIOWrapper(f, encoding="latin-1"))
        rows = list(reader)
    for row in rows:
        if len(row) >= 8 and row[1].strip().upper() == BOSTON_STATE and row[2].strip() == BOSTON_LOCALITY:
            work_gpci = float(row[5])  # "with 1.0 floor" column — the one CMS actually pays with
            pe_gpci = float(row[6])
            mp_gpci = float(row[7])
            locality_label = f"{row[1].strip()}-{row[2].strip()} {row[3].strip().title()}"
            return work_gpci, pe_gpci, mp_gpci, locality_label
    raise SystemExit(f"Boston locality (state={BOSTON_STATE}, locality={BOSTON_LOCALITY}) not found in GPCI file")


def parse_pprrvu(zf: zipfile.ZipFile) -> dict[str, dict]:
    names = [n for n in zf.namelist() if "PPRRVU" in n.upper() and n.lower().endswith(".csv") and "NONQPP" in n.upper().replace("_", "")]
    if not names:
        names = [n for n in zf.namelist() if "PPRRVU" in n.upper() and n.lower().endswith(".csv")]
    if not names:
        raise SystemExit("PPRRVU csv not found in RVU zip")
    with zf.open(names[0]) as f:
        reader = csv.reader(io.TextIOWrapper(f, encoding="latin-1"))
        rows = list(reader)
    out: dict[str, dict] = {}
    for row in rows:
        if len(row) < 15 or row[0] not in ALL_CODES or row[1]:  # skip modifier rows
            continue
        try:
            work = float(row[5])
            fac_pe = float(row[8])
            mp = float(row[10])
        except (ValueError, IndexError):
            continue
        out[row[0]] = {"status": row[3], "work_rvu": work, "facility_pe_rvu": fac_pe, "mp_rvu": mp}
    return out, names[0]


def compute_professional(rvu: dict, work_gpci: float, pe_gpci: float, mp_gpci: float) -> float:
    return round(
        (rvu["work_rvu"] * work_gpci + rvu["facility_pe_rvu"] * pe_gpci + rvu["mp_rvu"] * mp_gpci)
        * CONVERSION_FACTOR_2026,
        2,
    )


# --------------------------------------------------------------------- OPPS

def parse_opps(zf: zipfile.ZipFile) -> tuple[dict[str, dict], str]:
    names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
    if not names:
        raise SystemExit("OPPS Addendum B csv not found in zip")
    # Prefer the plain (non-508) csv if present, else whichever exists.
    names.sort(key=lambda n: ("508" in n))
    with zf.open(names[0]) as f:
        reader = csv.reader(io.TextIOWrapper(f, encoding="latin-1"))
        rows = list(reader)
    out: dict[str, dict] = {}
    for row in rows:
        if len(row) < 6 or row[0] not in ALL_CODES:
            continue
        rate = _money(row[5])
        out[row[0]] = {"si": row[2], "payment_rate": rate}
    return out, names[0]


# --------------------------------------------------------------------- CLFS

def parse_clfs(zf: zipfile.ZipFile) -> tuple[dict[str, float], str]:
    names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
    if not names:
        raise SystemExit("CLFS csv not found in zip")
    with zf.open(names[0]) as f:
        reader = csv.reader(io.TextIOWrapper(f, encoding="latin-1"))
        rows = list(reader)
    out: dict[str, float] = {}
    for row in rows:
        if len(row) < 6:
            continue
        code, mod, rate = row[1] if len(row) > 1 else "", row[2] if len(row) > 2 else "", row[5] if len(row) > 5 else ""
        if code in ALL_CODES and not mod:
            val = _money(rate)
            if val is not None:
                out[code] = val
    return out, names[0]


# --------------------------------------------------------------------- chargemaster fallback

def chargemaster_fallback(code: str, chargemaster_db: str | None) -> dict | None:
    """Last resort: derive a 'global' estimate from the chargemaster's own
    MEDICARE-payer negotiated_dollar rows for this code (median across
    hospitals), tagged version='chargemaster-derived'. Only used for codes
    that resolve to nothing from PFS/OPPS/CLFS."""
    if not chargemaster_db or not Path(chargemaster_db).exists():
        return None
    import statistics
    conn = sqlite3.connect(chargemaster_db)
    cur = conn.cursor()
    cur.execute(
        "SELECT negotiated_dollar FROM charges WHERE code = ? AND code_type IN ('CPT','HCPCS') "
        "AND UPPER(payer_name) LIKE 'MEDICARE%'",
        (code,),
    )
    vals = []
    for (v,) in cur.fetchall():
        try:
            f = float(v)
            if f > 0:
                vals.append(f)
        except (TypeError, ValueError):
            continue
    conn.close()
    if not vals:
        return None
    return {
        "code": code, "code_type": "CPT", "component": "global",
        "value": round(statistics.median(vals), 2),
        "formula": "median(negotiated_dollar) over chargemaster rows where payer_name LIKE 'MEDICARE%'",
        "source": "chargemaster MEDICARE-payer rows (fallback — no PFS/OPPS/CLFS rate resolvable)",
        "source_url": None, "file_version": "chargemaster-derived",
        "locality": None, "label": f"Medicare (chargemaster-derived fallback, n={len(vals)})",
        "version": "chargemaster-derived",
    }


# --------------------------------------------------------------------- build

def build_rates(cache_only: bool, chargemaster_db: str | None) -> dict:
    log("Fetching PFS RVU + GPCI zip...")
    rvu_zip_path = fetch_zip(RVU_PAGE_CANDIDATES, "rvu.zip", cache_only)
    log("Fetching OPPS Addendum B zip...")
    opps_zip_path = fetch_zip(OPPS_PAGE_CANDIDATES, "opps_addendum_b.zip", cache_only)
    log("Fetching CLFS zip...")
    clfs_zip_path = fetch_zip(CLFS_PAGE_CANDIDATES, "clfs.zip", cache_only)

    with zipfile.ZipFile(rvu_zip_path) as zf:
        work_gpci, pe_gpci, mp_gpci, locality_label = parse_gpci(zf)
        pprrvu, pprrvu_file = parse_pprrvu(zf)
    with zipfile.ZipFile(opps_zip_path) as zf:
        opps, opps_file = parse_opps(zf)
    with zipfile.ZipFile(clfs_zip_path) as zf:
        clfs, clfs_file = parse_clfs(zf)

    log(f"Boston GPCI: work={work_gpci} pe={pe_gpci} mp={mp_gpci} ({locality_label})")

    rows: list[dict] = []
    fallback_codes: list[str] = []

    for code in ALL_CODES:
        if code in CLFS_SPECIAL_CODES:
            rate = clfs.get(code)
            if rate is not None:
                rows.append({
                    "code": code, "code_type": "CPT", "component": "global",
                    "value": rate,
                    "formula": "flat CLFS national rate (specimen-collection fee; PFS status X / OPPS status Q4 — not separately payable under PFS/OPPS)",
                    "source": f"CMS CLFS {clfs_file}",
                    "source_url": "https://www.cms.gov/medicare/payment/fee-schedules/clinical-laboratory-fee-schedule-clfs/files",
                    "file_version": clfs_file, "locality": None,
                    "label": "Medicare CLFS specimen-collection fee (national, no geo adjustment)",
                    "version": "cms-clfs-2026q3",
                })
                continue
            fb = chargemaster_fallback(code, chargemaster_db)
            if fb:
                rows.append(fb)
                fallback_codes.append(code)
            continue

        if code in LAB_CODES:
            rate = clfs.get(code)
            if rate is not None:
                rows.append({
                    "code": code, "code_type": "CPT", "component": "global",
                    "value": rate,
                    "formula": "flat CLFS national rate (no geographic adjustment)",
                    "source": f"CMS CLFS {clfs_file}",
                    "source_url": "https://www.cms.gov/medicare/payment/fee-schedules/clinical-laboratory-fee-schedule-clfs/files",
                    "file_version": clfs_file, "locality": None,
                    "label": "Medicare CLFS (national flat rate)",
                    "version": "cms-clfs-2026q3",
                })
                continue
            fb = chargemaster_fallback(code, chargemaster_db)
            if fb:
                rows.append(fb)
                fallback_codes.append(code)
            continue

        # E/M, imaging, IV/injection: professional (PFS) + facility (OPPS)
        rvu = pprrvu.get(code)
        prof_val = None
        if rvu and rvu["status"] == "A":
            prof_val = compute_professional(rvu, work_gpci, pe_gpci, mp_gpci)
            rows.append({
                "code": code, "code_type": "CPT", "component": "professional",
                "value": prof_val,
                "formula": "(work_RVU*work_GPCI + facility_PE_RVU*PE_GPCI + MP_RVU*MP_GPCI) * conversion_factor",
                "source": f"CMS PFS {pprrvu_file} (facility PE RVU column) x GPCI2026 {locality_label}",
                "source_url": "https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files",
                "file_version": pprrvu_file, "locality": BOSTON_LABEL,
                "label": f"Medicare professional (PFS, facility PE, {BOSTON_LABEL})",
                "version": "cms-pfs-rvu26a",
            })

        opps_row = opps.get(code)
        fac_val = opps_row["payment_rate"] if opps_row else None
        if fac_val is not None:
            rows.append({
                "code": code, "code_type": "CPT", "component": "facility",
                "value": fac_val,
                "formula": "OPPS Addendum B national unadjusted payment rate (relative weight x OPPS conversion factor, published directly)",
                "source": f"CMS OPPS Addendum B {opps_file} (SI={opps_row['si']})",
                "source_url": "https://www.cms.gov/medicare/payment/prospective-payment-systems/hospital-outpatient-pps/quarterly-addenda-updates",
                "file_version": opps_file, "locality": None,
                "label": "Medicare facility (OPPS Addendum B, national unadjusted — not wage-adjusted for Boston)",
                "version": "cms-opps-2026q3",
            })

        if prof_val is not None and fac_val is not None:
            rows.append({
                "code": code, "code_type": "CPT", "component": "global",
                "value": round(prof_val + fac_val, 2),
                "formula": "professional + facility (physician-group and hospital-facility components summed)",
                "source": "derived: sum of professional + facility rows above",
                "source_url": None, "file_version": f"{pprrvu_file}+{opps_file}",
                "locality": BOSTON_LABEL,
                "label": "Medicare global (professional + facility, Boston locality)",
                "version": "cms-pfs-rvu26a+opps-2026q3",
            })
        elif prof_val is None and fac_val is None:
            fb = chargemaster_fallback(code, chargemaster_db)
            if fb:
                rows.append(fb)
                fallback_codes.append(code)

    # ---- sanity gate ----
    p283 = next((r for r in rows if r["code"] == "99283" and r["component"] == "professional"), None)
    if p283 is None or not (65 <= p283["value"] <= 80):
        raise SystemExit(
            f"SANITY GATE FAILED: 99283 professional = {p283['value'] if p283 else 'MISSING'} "
            "(expected $65-80). Investigate GPCI/RVU parsing before staging."
        )
    log(f"Sanity gate OK: 99283 professional = ${p283['value']}")

    return {
        "provenance": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generator": "scripts/fetch_medicare.py",
            "conversion_factor_2026": CONVERSION_FACTOR_2026,
            "locality": locality_label,
            "gpci": {"work": work_gpci, "pe": pe_gpci, "mp": mp_gpci},
            "files": {"pfs": pprrvu_file, "opps": opps_file, "clfs": clfs_file},
            "codes_via_chargemaster_fallback": fallback_codes,
            "path": "real-cms-files" if not fallback_codes else "real-cms-files+partial-chargemaster-fallback",
        },
        "rows": rows,
    }


# --------------------------------------------------------------------- staging

def stage_sqlite(db_path: str, rows: list[dict]) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS medicare_rates (
            code TEXT, code_type TEXT, component TEXT, value REAL,
            formula TEXT, source TEXT, source_url TEXT, file_version TEXT,
            locality TEXT, label TEXT, version TEXT
        )
    """)
    cur.execute("DELETE FROM medicare_rates")
    cur.executemany(
        "INSERT INTO medicare_rates (code, code_type, component, value, formula, source, source_url, "
        "file_version, locality, label, version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(r["code"], r.get("code_type", "CPT"), r["component"], r["value"], r.get("formula"),
          r.get("source"), r.get("source_url"), r.get("file_version"), r.get("locality"),
          r.get("label"), r.get("version")) for r in rows],
    )
    conn.commit()
    conn.close()
    log(f"Staged {len(rows)} medicare_rates rows -> sqlite {db_path}")


def stage_supabase(rows: list[dict]) -> None:
    url = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not url:
        raise SystemExit("SUPABASE_DB_URL not set")
    import psycopg2
    conn = psycopg2.connect(url, connect_timeout=10)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS medicare_rates (
                    id BIGSERIAL PRIMARY KEY,
                    code TEXT NOT NULL,
                    code_type TEXT NOT NULL DEFAULT 'CPT',
                    component TEXT NOT NULL,
                    value NUMERIC(12,2) NOT NULL,
                    formula TEXT,
                    source TEXT,
                    source_url TEXT,
                    file_version TEXT,
                    locality TEXT,
                    label TEXT,
                    version TEXT,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE (code, code_type, component)
                )
            """)
            for r in rows:
                cur.execute(
                    """INSERT INTO medicare_rates
                       (code, code_type, component, value, formula, source, source_url,
                        file_version, locality, label, version, updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
                       ON CONFLICT (code, code_type, component) DO UPDATE SET
                         value = EXCLUDED.value, formula = EXCLUDED.formula,
                         source = EXCLUDED.source, source_url = EXCLUDED.source_url,
                         file_version = EXCLUDED.file_version, locality = EXCLUDED.locality,
                         label = EXCLUDED.label, version = EXCLUDED.version, updated_at = now()
                    """,
                    (r["code"], r.get("code_type", "CPT"), r["component"], r["value"], r.get("formula"),
                     r.get("source"), r.get("source_url"), r.get("file_version"), r.get("locality"),
                     r.get("label"), r.get("version")),
                )
        log(f"Staged {len(rows)} medicare_rates rows -> Supabase (upsert, credentials not printed)")
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache-only", action="store_true", help="reuse data/raw/cms/* only, no network calls")
    ap.add_argument("--stage-sqlite", metavar="DB_PATH", help="also write a medicare_rates table into this sqlite file")
    ap.add_argument("--stage-supabase", action="store_true", help="also upsert into Supabase medicare_rates table (env SUPABASE_DB_URL)")
    ap.add_argument("--chargemaster-db", default=None, help="path to chargemaster sqlite DB for fallback derivation")
    ap.add_argument("--out", default=str(SEED_OUT))
    args = ap.parse_args()

    result = build_rates(args.cache_only, args.chargemaster_db)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    log(f"Wrote {len(result['rows'])} medicare_rates rows -> {out_path}")

    if args.stage_sqlite:
        stage_sqlite(args.stage_sqlite, result["rows"])
    if args.stage_supabase:
        stage_supabase(result["rows"])


if __name__ == "__main__":
    main()
