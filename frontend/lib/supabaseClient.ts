"use client";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  // Thrown at module load in dev so a missing .env.local fails loudly
  // instead of every OAuth click silently doing nothing.
  throw new Error(
    "Missing NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY. " +
      "Copy .env.local.example to .env.local and fill in the frontend's own Supabase project values " +
      "(same Supabase project the backend uses, but this is the public anon key, not a backend secret)."
  );
}

// Singleton client. persistSession (default true) writes the session to
// localStorage so a refresh doesn't log the user out; detectSessionInUrl
// (default true) is what lets the client pick up the ?code= param Supabase
// appends on the OAuth redirect and exchange it for a session automatically
// -- no server-side callback route needed for a client-only app like this.
export const supabase: SupabaseClient = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});
