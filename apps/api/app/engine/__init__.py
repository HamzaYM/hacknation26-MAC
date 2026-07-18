"""Deterministic engine core (PRD §7–§8).

Everything with a number, threshold, or legal claim lives here, driven by
config/verticals/<vertical>.yaml + seed tables. No LLM, no network, no DB:
  flags.py         — red-flag detection over JobSpec line items
  dossier.py       — StrategyDossier builder (route, levers, anchor/target/floor)
  state_machine.py — per-call ladder state machine (report_lever_result's brain)
"""
