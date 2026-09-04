import { memo } from "react";
import ReactMarkdown, {
  type Components,
} from "react-markdown";
import remarkGfm from "remark-gfm";

type MarkdownMessageProps = {
  content: string;
  isStreaming?: boolean;
};

const MARKDOWN_COMPONENTS: Components = {
  h1: ({ children }) => (
    <h1 className="mb-3 mt-5 text-lg font-semibold first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-2 mt-4 text-base font-semibold first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-2 mt-4 text-sm font-semibold first:mt-0">
      {children}
    </h3>
  ),
  p: ({ children }) => (
    <p className="mb-3 last:mb-0">
      {children}
    </p>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-[var(--aq-text)]">
      {children}
    </strong>
  ),
  ul: ({ children }) => (
    <ul className="my-3 list-disc space-y-1 pl-5">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="my-3 list-decimal space-y-1 pl-5">
      {children}
    </ol>
  ),
  li: ({ children }) => (
    <li className="pl-1">
      {children}
    </li>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-2 border-[var(--aq-blue)] pl-4 text-[var(--aq-muted)]">
      {children}
    </blockquote>
  ),
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-[var(--aq-blue)] underline underline-offset-2"
    >
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="rounded bg-black/30 px-1.5 py-0.5 font-mono text-[0.9em]">
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="my-3 overflow-x-auto rounded-xl border border-[var(--aq-border)] bg-black/30 p-4 text-xs leading-6">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="my-4 overflow-x-auto rounded-xl border border-[var(--aq-border)]">
      <table className="w-full border-collapse text-left text-xs">
        {children}
      </table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border-b border-[var(--aq-border)] bg-black/20 px-3 py-2 font-semibold text-[var(--aq-text)]">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border-b border-[var(--aq-border)] px-3 py-2 align-top">
      {children}
    </td>
  ),
  img: () => null,
};

const REMARK_PLUGINS = [remarkGfm];

export const MarkdownMessage = memo(function MarkdownMessage({
  content,
  isStreaming = false,
}: MarkdownMessageProps) {
  return (
    <div className="text-sm leading-7 text-[var(--aq-text-soft)]">
      <ReactMarkdown
        remarkPlugins={REMARK_PLUGINS}
        components={MARKDOWN_COMPONENTS}
        skipHtml
      >
        {content}
      </ReactMarkdown>

      {isStreaming ? (
        <span
          aria-hidden="true"
          className="animate-pulse text-[var(--aq-blue)]"
        >
          ▋
        </span>
      ) : null}
    </div>
  );
});
