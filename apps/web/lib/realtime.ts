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

/**
 * War Room multi-call overview: the full roster of calls for a case, with
 * each call's dossier target entity joined in. Calls onCalls with a fresh
 * id-ordered list on subscribe and again after every INSERT/UPDATE on the
 * case's calls (a refetch rather than a local merge — Realtime payloads
 * carry only the bare row, so refetching keeps the dossier join populated).
 */
export function subscribeToActiveCalls(caseId: string, onCalls: (calls: ActiveCall[]) => void) {
  let disposed = false;
  const fetchAll = () => {
    supabase
      .from("calls")
      .select("*, dossier:strategy_dossiers(target_entity, route)")
      .eq("case_id", caseId)
      .order("id")
      .then(({ data }) => {
        if (!disposed && data) onCalls(data as unknown as ActiveCall[]);
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
