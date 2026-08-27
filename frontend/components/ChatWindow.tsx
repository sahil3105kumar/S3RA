"use client";

import { useEffect, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { ApiError, sendChatMessage } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";
import { ChatMessageBubble } from "@/components/ChatMessageBubble";
import { ChatInput } from "@/components/ChatInput";

function newId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);
}

export function ChatWindow({ session }: { session: Session | null }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function handleSend(text: string) {
    const userMessage: ChatMessage = { id: newId(), role: "user", content: text };
    const pendingId = newId();

    setMessages((prev) => [...prev, userMessage, { id: pendingId, role: "assistant", content: "", pending: true }]);
    setSending(true);

    try {
      // Chat works with or without a session -- the access token is only
      // attached when one exists, matching the backend's optional-auth
      // contract (anonymous callers get web search only).
      const result = await sendChatMessage(text, session?.access_token);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingId
            ? {
                ...m,
                content: result.answer,
                toolsUsed: result.tool_used,
                sources: result.sources,
                pending: false,
              }
            : m
        )
      );
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Something went wrong reaching S3RA. Try again.";
      setMessages((prev) =>
        prev.map((m) => (m.id === pendingId ? { ...m, content: message, pending: false, error: true } : m))
      );
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="mx-auto flex h-full w-full max-w-4xl flex-col">
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-6 lg:px-8">
        {messages.length === 0 ? <EmptyState loggedIn={!!session} /> : null}
        {messages.map((m) => (
          <ChatMessageBubble key={m.id} message={m} />
        ))}
      </div>

      <div className="border-t border-ink-700 bg-ink-950/80 px-4 py-3.5 backdrop-blur lg:px-8">
        <ChatInput onSend={handleSend} disabled={sending} />
        <p className="mt-2 text-center text-[11px] text-ink-500">
          {session
            ? "Searches your documents and the live web."
            : "Answers use live web search only — sign in to also search your own documents."}
        </p>
      </div>
    </div>
  );
}

function EmptyState({ loggedIn }: { loggedIn: boolean }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 py-16 text-center">
      <p className="font-display text-lg font-semibold text-ink-100">Ask S3RA something</p>
      <p className="max-w-xs text-[13px] leading-relaxed text-ink-400">
        {loggedIn
          ? "It'll decide on its own whether to check your documents, search the web, both, or neither."
          : "No account needed to chat — sign in if you want it searching your own uploaded documents too."}
      </p>
    </div>
  );
}