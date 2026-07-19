// Falling-cash background for the marketing surface — geometry, colors, and
// the animation itself extracted directly from the reference mock's
// stylesheet ("ui mocks/Haggl Landing (5a + 5b).html", .hg-bill / @keyframes
// hg-fall): solid filled rounded rectangles with a "$" mark, NOT outlined
// icons — an earlier draft got the fill style wrong. 33 pieces, 3 color
// variants, all values (left/rotation/scale/duration/delay) are the mock's
// own instance data, not re-derived.
type Piece = { left: string; variant?: "hg-ink" | "hg-cream"; r: number; s: number; duration: number; delay: number };

const PIECES: Piece[] = [
  { left: "2%", r: -38, s: 0.95, duration: 5.5, delay: 0 },
  { left: "7%", variant: "hg-ink", r: 22, s: 0.7, duration: 7.8, delay: 2.1 },
  { left: "11%", variant: "hg-cream", r: -14, s: 1.1, duration: 4.6, delay: 0.8 },
  { left: "16%", r: 48, s: 0.8, duration: 6.9, delay: 3.4 },
  { left: "20%", variant: "hg-ink", r: -27, s: 1, duration: 5.1, delay: 1.3 },
  { left: "25%", variant: "hg-cream", r: 12, s: 0.85, duration: 8.3, delay: 0.2 },
  { left: "29%", r: -52, s: 1.15, duration: 6.2, delay: 2.7 },
  { left: "34%", variant: "hg-ink", r: 33, s: 0.75, duration: 4.9, delay: 4.2 },
  { left: "38%", r: -8, s: 0.95, duration: 7.4, delay: 1.6 },
  { left: "43%", variant: "hg-cream", r: 41, s: 1.05, duration: 5.7, delay: 0.5 },
  { left: "47%", variant: "hg-ink", r: -19, s: 0.8, duration: 6.6, delay: 3.1 },
  { left: "51%", r: 26, s: 1.2, duration: 4.4, delay: 2.3 },
  { left: "55%", variant: "hg-cream", r: -44, s: 0.9, duration: 8, delay: 0.9 },
  { left: "60%", variant: "hg-ink", r: 16, s: 0.7, duration: 5.9, delay: 4 },
  { left: "64%", r: -31, s: 1, duration: 6.8, delay: 1.1 },
  { left: "68%", variant: "hg-cream", r: 54, s: 0.85, duration: 4.7, delay: 2.9 },
  { left: "72%", variant: "hg-ink", r: -11, s: 1.1, duration: 7.1, delay: 0.4 },
  { left: "77%", r: 37, s: 0.9, duration: 5.3, delay: 3.7 },
  { left: "81%", variant: "hg-cream", r: -49, s: 0.75, duration: 8.6, delay: 1.8 },
  { left: "85%", variant: "hg-ink", r: 9, s: 1.05, duration: 6.1, delay: 0.7 },
  { left: "89%", r: -24, s: 0.95, duration: 4.8, delay: 2.5 },
  { left: "93%", variant: "hg-cream", r: 44, s: 0.8, duration: 7.6, delay: 1.4 },
  { left: "97%", variant: "hg-ink", r: -35, s: 1, duration: 5.6, delay: 3.9 },
  { left: "4%", r: 29, s: 0.7, duration: 6.4, delay: 4.6 },
  { left: "22%", variant: "hg-cream", r: -42, s: 1.1, duration: 5, delay: 5.1 },
  { left: "41%", variant: "hg-ink", r: 18, s: 0.85, duration: 7.9, delay: 5.4 },
  { left: "58%", r: -6, s: 0.95, duration: 5.4, delay: 4.9 },
  { left: "75%", variant: "hg-cream", r: 51, s: 0.75, duration: 6.7, delay: 5.8 },
  { left: "88%", variant: "hg-ink", r: -16, s: 1.15, duration: 4.5, delay: 5.3 },
  { left: "32%", r: 36, s: 0.9, duration: 8.1, delay: 6.2 },
  { left: "66%", variant: "hg-cream", r: -47, s: 0.8, duration: 5.2, delay: 6.6 },
  { left: "14%", variant: "hg-ink", r: 23, s: 1, duration: 6.9, delay: 6.9 },
];

export default function MoneyRain() {
  return (
    <div className="money-rain" aria-hidden="true">
      {PIECES.map((p, i) => (
        <div
          key={i}
          className={`hg-bill ${p.variant ?? ""}`}
          style={{
            left: p.left,
            animationDuration: `${p.duration}s`,
            animationDelay: `${p.delay}s`,
            // @ts-expect-error custom properties
            "--r": `${p.r}deg`,
            "--s": p.s,
          }}
        />
      ))}
    </div>
  );
}
