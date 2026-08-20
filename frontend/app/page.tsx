"use client";

import { useState } from "react";
import { useSession } from "@/hooks/useSession";
import { Header } from "@/components/Header";
import { ChatWindow } from "@/components/ChatWindow";
import { UploadPanel } from "@/components/UploadPanel";

export default function HomePage() {
  const { session, loading } = useSession();
  const [uploadOpen, setUploadOpen] = useState(false);

  return (
    <main className="flex h-dvh flex-col bg-ink-950">
      <Header session={session} sessionLoading={loading} onUploadClick={() => setUploadOpen(true)} />
      <div className="flex-1 overflow-hidden">
        <ChatWindow session={session} />
      </div>
      <UploadPanel session={session} open={uploadOpen} onClose={() => setUploadOpen(false)} />
    </main>
  );
}
