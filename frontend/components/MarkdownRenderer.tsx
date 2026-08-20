import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

// Maps markdown/HTML elements onto the app's existing dark theme (ink-*,
// signal) instead of pulling in @tailwind/typography, since this only
// needs to cover the handful of elements the model actually produces
// (headings, lists, emphasis, code, tables, blockquotes, links, math).
const components: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-ink-100">{children}</strong>,
  em: ({ children }) => <em className="italic text-ink-200">{children}</em>,
  ul: ({ children }) => <ul className="mb-2 ml-4 list-disc space-y-1 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal space-y-1 last:mb-0">{children}</ol>,
  li: ({ children }) => <li className="pl-1">{children}</li>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-signal underline underline-offset-2 hover:text-signal-bright"
    >
      {children}
    </a>
  ),
  code: ({ className, children, ...props }) => {
    // react-markdown only tags fenced code blocks with a `language-*`
    // className -- that's the one reliable signal to tell a multi-line
    // block apart from `inline code`, which needs different styling.
    const isBlock = /language-/.test(className ?? "");
    if (isBlock) {
      return (
        <code
          className={`block overflow-x-auto rounded-lg bg-ink-900 p-3 font-mono text-[13px] leading-relaxed text-ink-100 ${className ?? ""}`}
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <code className="rounded bg-ink-900 px-1.5 py-0.5 font-mono text-[13px] text-signal-bright" {...props}>
        {children}
      </code>
    );
  },
  pre: ({ children }) => <pre className="mb-2 overflow-x-auto last:mb-0">{children}</pre>,
  blockquote: ({ children }) => (
    <blockquote className="mb-2 border-l-2 border-signal/40 pl-3 italic text-ink-300 last:mb-0">
      {children}
    </blockquote>
  ),
  h1: ({ children }) => <h1 className="mb-2 mt-1 font-display text-base font-semibold text-ink-100">{children}</h1>,
  h2: ({ children }) => (
    <h2 className="mb-2 mt-1 font-display text-[15px] font-semibold text-ink-100">{children}</h2>
  ),
  h3: ({ children }) => <h3 className="mb-1.5 mt-1 font-display text-sm font-semibold text-ink-100">{children}</h3>,
  hr: () => <hr className="my-3 border-ink-700" />,
  table: ({ children }) => (
    <div className="mb-2 overflow-x-auto last:mb-0">
      <table className="w-full border-collapse text-left text-[13px]">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="border-b border-ink-600 text-ink-200">{children}</thead>,
  th: ({ children }) => <th className="px-2 py-1 font-medium">{children}</th>,
  td: ({ children }) => <td className="border-t border-ink-800 px-2 py-1 align-top">{children}</td>,
};

export function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div className="markdown-body [&_.katex]:text-[15px]">
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}