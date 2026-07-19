// The one fee line and the fee math, in one place, so landing, confirm, and the
// case file never drift. Mirrors the pricing card on /how-it-works.
export const FEE_RATE = 0.25;
export const FEE_CAP = 2000;

export const FEE_LINE =
  "We keep 25% of what we save you, capped at $2,000 per bill. $0 if we save you nothing.";

// Our fee on a given amount of savings: 25%, capped at $2,000, never below $0.
export function feeOn(savings: number): number {
  if (!(savings > 0)) return 0;
  return Math.min(Math.round(savings * FEE_RATE), FEE_CAP);
}

// What the patient keeps after our fee.
export function yourShare(savings: number): number {
  return Math.max(Math.round(savings) - feeOn(savings), 0);
}
