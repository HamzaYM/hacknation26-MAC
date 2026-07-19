"use client";

import { useState } from "react";

// Static demo queue — a real backend endpoint for "what's still missing per
// case" doesn't exist yet (financial_profile is currently filled in the fixture,
// so this queue is illustrative of the pattern, not live-computed). TODO(Hamza).
// Every "unlocks" line names a dollar or percent figure tied to a specific bill —
// pulled from the same numbers shown on that bill's detail page, never invented here.
const QUEUE = [
  {
    entity: "Mercy General Hospital",
    question: "Confirm your date of service",
    why: "Lets us match the itemized bill line-by-line against your insurance EOB.",
    unlocks: "Confirms the $412 (9.6%) duplicate-charge win already found on your Mercy General bill.",
  },
  {
    // Income itself is already known from onboarding's financial snapshot —
    // this item converts that data into a decision, not a re-ask. Repeating
    // the income question here (as an earlier draft did) is exactly the kind
    // of redundant-ask that undermines the "ask once" promise on /onboard.
    entity: "Mercy General Hospital",
    question: "You may qualify for charity care. Want us to apply?",
    why: "Based on the income range you gave us at signup, Mercy General (a nonprofit) likely has to offer you discounted or free care under federal rules (§501(r)).",
    unlocks: "Could add charity-care eligibility to your Mercy General bill: potentially 50–100% off the remaining $3,875 (~$1,938–$3,875).",
  },
  {
    entity: "Bay State Emergency Physicians",
    question: "Authorize us to dispute the ER physician charge",
    why: "This is a separate bill from a separate entity; we need your go-ahead per entity before we call.",
    unlocks: "Unlocks the call to Bay State Emergency Physicians: typical range is 15–35% off their $640 balance (~$96–$224).",
  },
  {
    entity: "Meridian Recovery Services",
    question: "Authorize us to negotiate your collections account",
    why: "Collections settlements need explicit authorization since a lump-sum offer is binding once accepted.",
    unlocks: "Unlocks settlement negotiation on your $980 collections balance: typically 25–50% off (~$245–$490) via lump-sum settlement.",
  },
];

export default function ActionItems() {
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);

  const item = QUEUE[index];
  const done = index >= QUEUE.length;

  function next() {
    setSelected(null);
    setIndex((i) => Math.min(i + 1, QUEUE.length));
  }

  return (
    <div>
      <div className="user-strip">
        <span>Action Items</span>
      </div>

      {done ? (
        <div className="action-card" style={{ textAlign: "center" }}>
          <h2>You&apos;re all caught up</h2>
          <p style={{ color: "var(--text-secondary)" }}>
            We&apos;ll ping you here the next time we need something to keep negotiating.
          </p>
          <a href="/bills" className="btn btn-primary" style={{ textDecoration: "none", marginTop: 16, display: "inline-flex" }}>
            Back to your bills
          </a>
        </div>
      ) : (
        <div className="action-card">
          <div className="eyebrow">Question · {item.entity}</div>
          <h2>{item.question}</h2>

          <div className="action-why">
            <strong>Why we&apos;re asking</strong>
            {item.why}
          </div>

          <div className="action-unlocks">
            <strong>Unlocks</strong>
            {item.unlocks}
          </div>

          <div className="action-options">
            <button className={`action-option ${selected === "yes" ? "selected" : ""}`} onClick={() => setSelected("yes")}>
              Yes, go ahead
            </button>
          </div>

          <button className="btn btn-primary" style={{ width: "100%" }} onClick={next} disabled={!selected}>
            Next →
          </button>

          <div className="action-progress">{index + 1} of {QUEUE.length}</div>
        </div>
      )}
    </div>
  );
}
