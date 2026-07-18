// Decorative falling-cash background for the marketing surface only.
// Positions are a fixed preset (not Math.random()) so server/client markup matches on hydration.
// Two-tone outline style + density calibrated against the reference mock (warm
// gray + dusty pink bills/coins, densely scattered edge-to-edge).

const BILL = (
  <svg width="64" height="37" viewBox="0 0 64 37" fill="none">
    <rect x="1" y="1" width="62" height="35" rx="5" stroke="currentColor" strokeWidth="2" fill="none" />
    <circle cx="32" cy="18.5" r="8.5" stroke="currentColor" strokeWidth="1.6" />
    <text x="32" y="23.5" fontSize="12" fontFamily="var(--font-mono)" textAnchor="middle" fill="currentColor">$</text>
  </svg>
);

const COIN = (
  <svg width="34" height="34" viewBox="0 0 34 34" fill="none">
    <rect x="1" y="1" width="32" height="32" rx="16" stroke="currentColor" strokeWidth="2" />
    <text x="17" y="22.5" fontSize="14" fontFamily="var(--font-mono)" textAnchor="middle" fill="currentColor">$</text>
  </svg>
);

const WARM = "var(--money-warm)";
const PINK = "var(--money-pink)";

type Piece = {
  left: string;
  size: "bill" | "coin";
  color: string;
  duration: number;
  delay: number;
  rotFrom: number;
  rotTo: number;
  scale: number;
};

// left position, color, and delay are hand-staggered so the page reads as
// densely scattered at any single instant, not a sparse trickle.
const PIECES: Piece[] = [
  { left: "1%", size: "coin", color: WARM, duration: 15, delay: -3, rotFrom: -10, rotTo: 14, scale: 0.85 },
  { left: "6%", size: "bill", color: PINK, duration: 19, delay: -11, rotFrom: 6, rotTo: -12, scale: 1 },
  { left: "11%", size: "coin", color: WARM, duration: 13, delay: -6, rotFrom: -14, rotTo: 8, scale: 0.9 },
  { left: "16%", size: "bill", color: WARM, duration: 17, delay: -1, rotFrom: 10, rotTo: -6, scale: 0.8 },
  { left: "21%", size: "coin", color: PINK, duration: 14, delay: -9, rotFrom: -8, rotTo: 16, scale: 0.95 },
  { left: "26%", size: "bill", color: WARM, duration: 21, delay: -14, rotFrom: 4, rotTo: -10, scale: 0.9 },
  { left: "31%", size: "coin", color: WARM, duration: 12, delay: -4, rotFrom: -12, rotTo: 10, scale: 0.85 },
  { left: "36%", size: "bill", color: PINK, duration: 18, delay: -16, rotFrom: 8, rotTo: -14, scale: 1.05 },
  { left: "41%", size: "coin", color: WARM, duration: 16, delay: -8, rotFrom: -6, rotTo: 12, scale: 0.8 },
  { left: "46%", size: "bill", color: WARM, duration: 20, delay: -2, rotFrom: 12, rotTo: -8, scale: 0.95 },
  { left: "51%", size: "coin", color: PINK, duration: 13, delay: -12, rotFrom: -10, rotTo: 14, scale: 0.9 },
  { left: "56%", size: "bill", color: WARM, duration: 22, delay: -6, rotFrom: 6, rotTo: -12, scale: 1 },
  { left: "61%", size: "coin", color: WARM, duration: 15, delay: -17, rotFrom: -14, rotTo: 8, scale: 0.85 },
  { left: "66%", size: "bill", color: PINK, duration: 19, delay: -3, rotFrom: 10, rotTo: -6, scale: 0.85 },
  { left: "71%", size: "coin", color: WARM, duration: 14, delay: -10, rotFrom: -8, rotTo: 16, scale: 0.9 },
  { left: "76%", size: "bill", color: WARM, duration: 23, delay: -5, rotFrom: 4, rotTo: -10, scale: 1.05 },
  { left: "81%", size: "coin", color: PINK, duration: 12, delay: -15, rotFrom: -12, rotTo: 10, scale: 0.8 },
  { left: "86%", size: "bill", color: WARM, duration: 18, delay: -7, rotFrom: 8, rotTo: -14, scale: 0.9 },
  { left: "91%", size: "coin", color: WARM, duration: 16, delay: -13, rotFrom: -6, rotTo: 12, scale: 0.95 },
  { left: "96%", size: "bill", color: PINK, duration: 21, delay: -1, rotFrom: 12, rotTo: -8, scale: 1 },
  { left: "4%", size: "bill", color: WARM, duration: 25, delay: -19, rotFrom: -4, rotTo: 10, scale: 0.85 },
  { left: "24%", size: "coin", color: PINK, duration: 17, delay: -18, rotFrom: 10, rotTo: -6, scale: 0.9 },
  { left: "44%", size: "bill", color: WARM, duration: 20, delay: -20, rotFrom: -6, rotTo: 12, scale: 0.8 },
  { left: "64%", size: "coin", color: WARM, duration: 15, delay: -21, rotFrom: 8, rotTo: -14, scale: 0.95 },
  { left: "84%", size: "bill", color: PINK, duration: 19, delay: -22, rotFrom: -10, rotTo: 14, scale: 0.9 },
  { left: "94%", size: "coin", color: WARM, duration: 14, delay: -10, rotFrom: 6, rotTo: -12, scale: 0.85 },
];

export default function MoneyRain() {
  return (
    <div className="money-rain" aria-hidden="true">
      {PIECES.map((p, i) => (
        <div
          key={i}
          className="bill"
          style={{
            left: p.left,
            color: p.color,
            animationDuration: `${p.duration}s`,
            animationDelay: `${p.delay}s`,
            // @ts-expect-error custom properties
            "--rot-from": `${p.rotFrom}deg`,
            "--rot-to": `${p.rotTo}deg`,
          }}
        >
          {/* separate element for the static scale — the fall animation owns `transform` on the parent */}
          <div style={{ transform: `scale(${p.scale})` }}>{p.size === "bill" ? BILL : COIN}</div>
        </div>
      ))}
    </div>
  );
}
