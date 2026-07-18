import { supabase } from "./supabase";
import type { Call, CallEvent } from "./types";

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
