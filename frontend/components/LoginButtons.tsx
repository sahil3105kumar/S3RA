"use client";

import { useState } from "react";
import { supabase } from "@/lib/supabaseClient";

type Provider = "google" | "github";

interface LoginButtonsProps {
  compact?: boolean;
  onStart?: () => void;
}

/**
 * The only sign-in surface in the app. Deliberately has no email/password
 * fields -- Supabase Auth is configured for Google/GitHub OAuth only, so
 * there's nothing for a password form to submit to.
 */
export function LoginButtons({ compact = false, onStart }: LoginButtonsProps) {
  const [pending, setPending] = useState<Provider | null>(null);

  async function signIn(provider: Provider) {
    setPending(provider);
    onStart?.();
    const { error } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });
    if (error) {
      // Redirect away from the page is the normal success path, so
      // reaching this line at all means the OAuth kickoff itself failed.
      console.error(`${provider} sign-in failed:`, error.message);
      setPending(null);
    }
  }

  return (
    <div className={`flex ${compact ? "flex-row gap-2" : "flex-col gap-2.5"}`}>
      <button
        type="button"
        onClick={() => signIn("google")}
        disabled={pending !== null}
        className="focus-ring group flex items-center justify-center gap-2.5 rounded-lg border border-ink-600 bg-ink-800 px-4 py-2.5 text-sm font-medium text-ink-100 transition hover:border-ink-500 hover:bg-ink-700 disabled:cursor-wait disabled:opacity-60"
      >
        <GoogleMark />
        {pending === "google" ? "Redirecting…" : "Continue with Google"}
      </button>
      <button
        type="button"
        onClick={() => signIn("github")}
        disabled={pending !== null}
        className="focus-ring group flex items-center justify-center gap-2.5 rounded-lg border border-ink-600 bg-ink-800 px-4 py-2.5 text-sm font-medium text-ink-100 transition hover:border-ink-500 hover:bg-ink-700 disabled:cursor-wait disabled:opacity-60"
      >
        <GitHubMark />
        {pending === "github" ? "Redirecting…" : "Continue with GitHub"}
      </button>
    </div>
  );
}

function GoogleMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M23.52 12.27c0-.85-.08-1.67-.22-2.45H12v4.64h6.47a5.53 5.53 0 0 1-2.4 3.63v3h3.88c2.27-2.09 3.57-5.17 3.57-8.82Z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.96-1.07 7.95-2.91l-3.88-3c-1.08.72-2.46 1.15-4.07 1.15-3.13 0-5.78-2.11-6.73-4.96H1.26v3.1A12 12 0 0 0 12 24Z"
      />
      <path
        fill="#FBBC05"
        d="M5.27 14.28A7.2 7.2 0 0 1 4.89 12c0-.79.14-1.56.38-2.28v-3.1H1.26A12 12 0 0 0 0 12c0 1.94.46 3.77 1.26 5.38l4.01-3.1Z"
      />
      <path
        fill="#EA4335"
        d="M12 4.77c1.77 0 3.35.61 4.6 1.8l3.44-3.44C17.95 1.19 15.24 0 12 0A12 12 0 0 0 1.26 6.62l4.01 3.1C6.22 6.88 8.87 4.77 12 4.77Z"
      />
    </svg>
  );
}

function GitHubMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 .5C5.65.5.5 5.66.5 12.03c0 5.1 3.29 9.42 7.86 10.95.57.1.78-.25.78-.55 0-.27-.01-1.17-.02-2.12-3.2.7-3.87-1.36-3.87-1.36-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.71.08-.71 1.17.08 1.78 1.2 1.78 1.2 1.03 1.77 2.71 1.26 3.37.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.79 0c2.2-1.49 3.17-1.18 3.17-1.18.64 1.59.24 2.76.12 3.05.74.81 1.19 1.83 1.19 3.09 0 4.42-2.69 5.4-5.25 5.68.41.36.78 1.08.78 2.17 0 1.57-.01 2.83-.01 3.22 0 .3.2.66.79.55A10.53 10.53 0 0 0 23.5 12.03C23.5 5.66 18.35.5 12 .5Z" />
    </svg>
  );
}
