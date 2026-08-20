"use client";

import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabaseClient";

interface SessionState {
  session: Session | null;
  loading: boolean;
}

/**
 * Client-side session state, kept in sync with Supabase.
 *
 * - On mount, reads whatever session is already in localStorage (fast,
 *   no network) and also picks up a session from an OAuth redirect's
 *   ?code= param (Supabase's client resolves that internally).
 * - Subscribes to onAuthStateChange so every tab/component reacts the
 *   moment sign-in/sign-out happens, without prop-drilling.
 */
export function useSession(): SessionState {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return;
      setSession(data.session);
      setLoading(false);
    });

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      if (!mounted) return;
      setSession(nextSession);
      setLoading(false);
    });

    return () => {
      mounted = false;
      subscription.subscription.unsubscribe();
    };
  }, []);

  return { session, loading };
}
