"use client";

import { useState } from "react";
import { ACTION_ITEMS } from "../../lib/actionItems";
import ActionItemCard from "../../components/ActionItemCard";

export default function ActionItems() {
  const [completed, setCompleted] = useState<Set<string>>(new Set());
  const [view, setView] = useState<"focus" | "bulk">("focus");

  const pending = ACTION_ITEMS.filter((i) => !completed.has(i.id));
  const easyCount = pending.filter((i) => i.type === "confirm").length;

  function complete(id: string) {
    setCompleted((prev) => new Set(prev).add(id));
  }

  function clearEasyOnes() {
    setCompleted((prev) => {
      const next = new Set(prev);
      pending.filter((i) => i.type === "confirm").forEach((i) => next.add(i.id));
      return next;
    });
  }

  return (
    <div>
      <div className="bulk-toolbar">
        <span className="user-strip" style={{ padding: 0 }}>
          Action Items {pending.length > 0 && <span className="pill pill-muted" style={{ marginLeft: 8 }}>{pending.length} pending</span>}
        </span>
        {pending.length > 0 && (
          <div className="view-toggle">
            <button className={view === "focus" ? "active" : ""} onClick={() => setView("focus")}>
              One at a time
            </button>
            <button className={view === "bulk" ? "active" : ""} onClick={() => setView("bulk")}>
              Clear in bulk
            </button>
          </div>
        )}
      </div>

      {pending.length === 0 ? (
        <div className="action-card" style={{ textAlign: "center" }}>
          <h2>You&apos;re all caught up</h2>
          <p style={{ color: "var(--text-secondary)" }}>
            We&apos;ll ping you here the next time we need something to keep negotiating.
          </p>
          <a href="/bills" className="btn btn-primary" style={{ textDecoration: "none", marginTop: 16, display: "inline-flex" }}>
            Back to your bills
          </a>
        </div>
      ) : view === "focus" ? (
        <>
          <ActionItemCard key={pending[0].id} item={pending[0]} onComplete={() => complete(pending[0].id)} />
          <div className="action-progress">{ACTION_ITEMS.length - pending.length + 1} of {ACTION_ITEMS.length}</div>
        </>
      ) : (
        <div>
          {easyCount > 0 && (
            <button className="btn btn-secondary" style={{ marginBottom: 16 }} onClick={clearEasyOnes}>
              Clear {easyCount} simple {easyCount === 1 ? "confirmation" : "confirmations"} at once →
            </button>
          )}
          {pending.map((item) => (
            <ActionItemCard key={item.id} item={item} onComplete={() => complete(item.id)} compact />
          ))}
        </div>
      )}
    </div>
  );
}
