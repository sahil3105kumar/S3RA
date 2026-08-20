import type { ChatMessage } from "@/lib/types";
import { ToolBadges } from "@/components/ToolBadges";
import { SourceList } from "@/components/SourceList";

export function ChatMessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex animate-rise ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`flex max-w-[85%] flex-col gap-1.5 sm:max-w-[70%] ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={`whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-[14px] leading-relaxed ${
            isUser
              ? "rounded-br-sm bg-signal/15 text-ink-100"
              : message.error
                ? "rounded-bl-sm border border-red-500/30 bg-red-500/10 text-red-200"
                : "rounded-bl-sm border border-ink-700 bg-ink-800 text-ink-100"
          }`}
        >
          {message.pending ? <ThinkingDots /> : message.content}
        </div>

        {!isUser && !message.pending && message.toolsUsed && message.toolsUsed.length > 0 && (
          <ToolBadges tools={message.toolsUsed} />
        )}

        {!isUser && !message.pending && message.sources && message.sources.length > 0 && (
          <SourceList sources={message.sources} />
        )}
      </div>
    </div>
  );
}

function ThinkingDots() {
  return (
    <span className="flex items-center gap-2 text-ink-300">
      <span className="flex gap-1">
        <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-signal [animation-delay:-0.32s]" />
        <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-signal [animation-delay:-0.16s]" />
        <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-signal" />
      </span>
      agent is thinking…
    </span>
  );
}
