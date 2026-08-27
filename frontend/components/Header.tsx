"use client";

import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabaseClient";

interface HeaderProps {
  session: Session | null;
  sessionLoading: boolean;
  onUploadClick: () => void;
}

export function Header({ session, sessionLoading, onUploadClick }: HeaderProps) {
  const identity = session?.user?.user_metadata?.full_name ?? session?.user?.email ?? null;
  const avatarUrl = session?.user?.user_metadata?.avatar_url as string | undefined;

  return (
    <header className="flex items-center justify-between border-b border-ink-700 bg-ink-950/80 px-5 py-3.5 backdrop-blur">
      <div className="flex items-center gap-2.5">
        <SignalMark />
        <div className="leading-tight">
          <p className="font-display text-[15px] font-semibold tracking-tight text-ink-100">S3RA</p>
          <p className="hidden text-[11px] text-ink-400 sm:block">docs + live web, one agent</p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onUploadClick}
          className="focus-ring flex items-center gap-1.5 rounded-md border border-ink-600 px-3 py-1.5 text-[13px] font-medium text-ink-200 transition hover:border-signal/50 hover:text-signal"
        >
          <UploadGlyph />
          Upload
        </button>

        {sessionLoading ? (
          <div className="h-8 w-8 animate-pulse rounded-full bg-ink-700" />
        ) : session ? (
          <div className="flex items-center gap-2">
            {avatarUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={avatarUrl}
                alt=""
                className="h-8 w-8 rounded-full border border-ink-600 object-cover"
                referrerPolicy="no-referrer"
              />
            ) : (
              <div className="flex h-8 w-8 items-center justify-center rounded-full border border-ink-600 bg-ink-800 text-[11px] font-medium text-ink-200">
                {identity?.[0]?.toUpperCase() ?? "?"}
              </div>
            )}
            <button
              type="button"
              onClick={() => supabase.auth.signOut()}
              className="focus-ring hidden rounded-md px-2.5 py-1.5 text-[13px] text-ink-400 transition hover:text-ink-100 sm:block"
            >
              Sign out
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}

function SignalMark() {
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" fill="none" aria-hidden="true">
      <circle cx="13" cy="13" r="12" stroke="#4d4033" strokeWidth="1.5" />
      <circle cx="13" cy="13" r="7.5" stroke="#e0904a" strokeWidth="1.5" opacity="0.55" />
      <circle cx="13" cy="13" r="2.2" fill="#e0904a" />
    </svg>
  );
}

function UploadGlyph() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 16V4m0 0L7 9m5-5 5 5M5 17v2a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-2"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}