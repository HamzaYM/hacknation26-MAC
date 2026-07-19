"use client";

import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "./supabase";

// Session state for client components. null = logged out (and the first
// render tick before the stored session hydrates). Deliberately NO route
// guards anywhere — logged-out visitors keep full access to every screen
// (demo safety); auth only adds identity to the chrome.
export function useSession(): Session | null {
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => sub.subscription.unsubscribe();
  }, []);

  return session;
}

// Returns a user-facing error message, or null on success.
export async function signInWithPassword(email: string, password: string): Promise<string | null> {
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (!error) return null;
  return error.message === "Invalid login credentials"
    ? "That email and password don't match. Check them and try again."
    : "Couldn't log you in: " + error.message;
}

export async function signOut(): Promise<void> {
  await supabase.auth.signOut();
}
