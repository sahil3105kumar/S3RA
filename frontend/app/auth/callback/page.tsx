"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

/**
 * google and github oauth redirect lands here.
 * supabase browser client exchanges code from url for session.
 * this page waits for session then routes back to chat.
 */
export default function AuthCallbackPage() {
  const router = useRouter();
  const [errored, setErrored] = useState(false);

  useEffect(() => {
    let settled = false;

    const { data: subscription } = supabase.auth.onAuthStateChange((event) => {
      if (settled) return;
      if (event === "SIGNED_IN") {
        settled = true;
        router.replace("/");
      }
    });

    // session may already resolve before listener attaches.
    supabase.auth.getSession().then(({ data }) => {
      if (settled) return;
      if (data.session) {
        settled = true;
        router.replace("/");
      }
    });

    const timeout = setTimeout(() => {
      if (!settled) setErrored(true);
    }, 8000);

    return () => {
      subscription.subscription.unsubscribe();
      clearTimeout(timeout);
    };
  }, [router]);

  return (
    <main className="flex h-dvh flex-col items-center justify-center gap-3 bg-ink-950 px-4 text-center">
      {errored ? (
        <>
          <p className="font-display text-[15px] font-semibold text-ink-100">Sign-in is taking longer than expected</p>
          <p className="text-[13px] text-ink-400">Something may have gone wrong with the redirect.</p>
          <a href="/" className="focus-ring mt-1 rounded-md border border-ink-600 px-4 py-2 text-[13px] text-ink-200 hover:border-signal/50 hover:text-signal">
            Back to S3RA
          </a>
        </>
      ) : (
        <>
          <span className="h-6 w-6 animate-spin rounded-full border-2 border-ink-600 border-t-signal" />
          <p className="text-[13px] text-ink-400">Finishing sign-in…</p>
        </>
      )}
    </main>
  );
}
