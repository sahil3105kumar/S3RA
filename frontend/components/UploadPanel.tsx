"use client";

import { useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { ApiError, uploadDocument } from "@/lib/api";
import { LoginButtons } from "@/components/LoginButtons";

interface UploadPanelProps {
  session: Session | null;
  open: boolean;
  onClose: () => void;
}

type UploadState =
  | { status: "idle" }
  | { status: "uploading"; filename: string }
  | { status: "done"; filename: string; chunks: number }
  | { status: "error"; filename: string; message: string };

export function UploadPanel({ session, open, onClose }: UploadPanelProps) {
  const [state, setState] = useState<UploadState>({ status: "idle" });
  const inputRef = useRef<HTMLInputElement>(null);

  if (!open) return null;

  async function handleFile(file: File) {
    // Belt-and-suspenders: the panel only renders its dropzone when
    // session is set, but the access token is re-read here rather than
    // trusted from closure in case it expired between render and click.
    if (!session) return;
    setState({ status: "uploading", filename: file.name });
    try {
      const result = await uploadDocument(file, session.access_token);
      setState({ status: "done", filename: result.filename, chunks: result.chunks_inserted });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Upload failed. Try again.";
      setState({ status: "error", filename: file.name, message });
    }
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center bg-ink-950/70 px-4 pt-24 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md animate-rise rounded-xl border border-ink-600 bg-ink-900 p-5 shadow-glow"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-[15px] font-semibold text-ink-100">Upload a document</h2>
          <button
            type="button"
            onClick={onClose}
            className="focus-ring rounded-md px-1.5 py-1 text-ink-400 hover:text-ink-100"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {!session ? (
          <div className="space-y-3">
            <p className="text-[13px] leading-relaxed text-ink-300">
              Uploads are tied to your account so only you can search your own documents. Sign in to continue.
            </p>
            <LoginButtons onStart={onClose} />
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-[13px] leading-relaxed text-ink-300">
              PDFs are chunked, embedded, and stored under your account only — no one else can search them.
            </p>

            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.txt,.md"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFile(file);
                e.target.value = "";
              }}
            />

            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              disabled={state.status === "uploading"}
              className="focus-ring flex w-full flex-col items-center gap-1.5 rounded-lg border border-dashed border-ink-500 px-4 py-8 text-center transition hover:border-signal/60 hover:bg-ink-800/60 disabled:cursor-wait disabled:opacity-70"
            >
              <span className="text-[13px] font-medium text-ink-100">
                {state.status === "uploading" ? `Uploading ${state.filename}…` : "Click to choose a file"}
              </span>
              <span className="text-[11px] text-ink-400">PDF, TXT, or MD</span>
            </button>

            {state.status === "done" && (
              <p className="rounded-md border border-signal/30 bg-signal/10 px-3 py-2 text-[12.5px] text-signal">
                {state.filename} indexed — {state.chunks} chunk{state.chunks === 1 ? "" : "s"} added.
              </p>
            )}
            {state.status === "error" && (
              <p className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-[12.5px] text-red-300">
                {state.message}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
