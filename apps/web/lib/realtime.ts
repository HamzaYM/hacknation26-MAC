import { supabase } from "./supabase";
import type { ActiveCall, Call, CallEvent } from "./types";

/**
 * War Room primary feed: typed milestone events for one call.
 * (contract: contracts — call_events; types in lib/types.ts)
 */
export function subscribeToCallEvents(callId: string, onEvent: (event: CallEvent) => void) {
  const channel = supabase
    .channel(`call_events:${callId}`)
    .on(
      "postgres_changes",
      { event: "INSERT", schema: "public", table: "call_events", filter: `call_id=eq.${callId}` },
      (payload) => onEvent(payload.new as unknown as CallEvent)
    )
    .subscribe();
  return () => supabase.removeChannel(channel);
}

/** Row-level status changes (queued → ringing → live → ended/failed). */
export function subscribeToCall(callId: string, onChange: (call: Call) => void) {
  const channel = supabase
    .channel(`calls:${callId}`)
    .on(
      "postgres_changes",
      { event: "UPDATE", schema: "public", table: "calls", filter: `id=eq.${callId}` },
      (payload) => onChange(payload.new as unknown as Call)
    )
    .subscribe();
  return () => supabase.removeChannel(channel);
}

// A non-terminal call that has produced ZERO events and has been dialing for
// more than ~10 minutes is a stale orphan (a launch that never streamed, the
// old ca11 fallback row), not a live negotiation — drop it from the overview
// so it doesn't linger as a dead "connecting…" card. A call with even one
// event, or one not yet dialed (no started_at — just launched, about to dial),
// is always kept, so the fresh confirm→launch flow shows its cards instantly.
const STALE_ZERO_EVENT_MS = 10 * 60 * 1000;
type CallWithEventCount = ActiveCall & { call_events?: { count: number }[] };
function isStaleZeroEventOrphan(call: CallWithEventCount): boolean {
  if (call.status === "ended" || call.status === "failed") return false;
  if ((call.call_events?.[0]?.count ?? 0) > 0) return false;
  if (!call.started_at) return false;
  return Date.now() - new Date(call.started_at).getTime() > STALE_ZERO_EVENT_MS;
}

/**
 * War Room multi-call overview: the full roster of calls for a case, with
 * each call's dossier target entity joined in. Calls onCalls with a fresh
 * id-ordered list on subscribe and again after every INSERT/UPDATE on the
 * case's calls (a refetch rather than a local merge — Realtime payloads
 * carry only the bare row, so refetching keeps the dossier join populated).
 * Stale zero-event orphans are filtered out here (see isStaleZeroEventOrphan).
 */
export function subscribeToActiveCalls(caseId: string, onCalls: (calls: ActiveCall[]) => void) {
  let disposed = false;
  const fetchAll = () => {
    supabase
      .from("calls")
      .select("*, dossier:strategy_dossiers(target_entity, route), call_events(count)")
      .eq("case_id", caseId)
      .order("id")
      .then(({ data }) => {
        if (disposed || !data) return;
        const calls = (data as unknown as CallWithEventCount[]).filter((c) => !isStaleZeroEventOrphan(c));
        onCalls(calls);
      });
  };
  fetchAll();
  const channel = supabase
    .channel(`calls:case:${caseId}:overview`)
    .on(
      "postgres_changes",
      { event: "INSERT", schema: "public", table: "calls", filter: `case_id=eq.${caseId}` },
      fetchAll
    )
    .on(
      "postgres_changes",
      { event: "UPDATE", schema: "public", table: "calls", filter: `case_id=eq.${caseId}` },
      fetchAll
    )
    .subscribe();
  return () => {
    disposed = true;
    supabase.removeChannel(channel);
  };
}

/**
 * All persisted events for one call, id-ordered — seeds a view opened
 * mid-call, which then stays live via subscribeToCallEvents.
 */
export async function fetchCallEvents(callId: string): Promise<CallEvent[]> {
  const { data, error } = await supabase
    .from("call_events")
    .select("*")
    .eq("call_id", callId)
    .order("id");
  if (error) return [];
  return (data ?? []) as unknown as CallEvent[];
}

/**
 * Whether ANY call for this case is currently ringing/live — what a bill
 * detail screen needs to know before it can honestly show a "live call"
 * card (vs. one that claims a call is happening when nothing is). Fires on
 * both INSERT (call just launched) and UPDATE (status changed).
 */
export function subscribeToCallsForCase(caseId: string, onChange: (call: Call) => void) {
  const channel = supabase
    .channel(`calls:case:${caseId}`)
    .on(
      "postgres_changes",
      { event: "INSERT", schema: "public", table: "calls", filter: `case_id=eq.${caseId}` },
      (payload) => onChange(payload.new as unknown as Call)
    )
    .on(
      "postgres_changes",
      { event: "UPDATE", schema: "public", table: "calls", filter: `case_id=eq.${caseId}` },
      (payload) => onChange(payload.new as unknown as Call)
    )
    .subscribe();
  return () => supabase.removeChannel(channel);
}
