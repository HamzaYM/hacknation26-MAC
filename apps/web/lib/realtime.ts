import { supabase } from "./supabase";

/**
 * War Room primary feed: typed milestone events for one call.
 * (contract: contracts — call_events; types in lib/types.ts)
 */
export function subscribeToCallEvents(
  callId: string,
  onEvent: (event: Record<string, unknown>) => void
) {
  const channel = supabase
    .channel(`call_events:${callId}`)
    .on(
      "postgres_changes",
      { event: "INSERT", schema: "public", table: "call_events", filter: `call_id=eq.${callId}` },
      (payload) => onEvent(payload.new as Record<string, unknown>)
    )
    .subscribe();
  return () => supabase.removeChannel(channel);
}
