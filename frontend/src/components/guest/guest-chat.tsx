"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { ArrowUp, LockKeyhole, Paperclip, Sparkles } from "lucide-react";

import { AqlyraLogo } from "@/components/brand/aqlyra-logo";

type Turn = { role: "user" | "assistant"; content: string };
type GuestResponse = {
  answer?: string;
  detail?: string;
  hourly_limit?: number;
};

export function GuestChat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [message, setMessage] = useState("");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [usage, setUsage] = useState(5);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = message.trim();
    if (!text || working) return;
    setWorking(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch("/api/guest/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history: turns.slice(-4) }),
      });
      const data = (await response.json()) as GuestResponse;
      if (!response.ok || typeof data.answer !== "string") {
        setMessage(text);
        setError(
          response.status === 429
            ? "Guest limit reached. Sign up for a full Aqlyra account."
            : data.detail ?? "Guest AI is unavailable right now.",
        );
        return;
      }
      if (typeof data.hourly_limit === "number") {
        setUsage(data.hourly_limit);
      }
      setTurns((old) => [
        ...old, { role: "user", content: text },
        { role: "assistant", content: data.answer ?? "" },
      ]);
    } catch {
      setMessage(text);
      setError("Unable to connect to Aqlyra guest chat.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col bg-[#080b12] text-[var(--aq-text)]">
      <header className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-4 sm:px-8">
        <AqlyraLogo size={36} />
        <nav className="flex items-center gap-3 text-xs font-semibold sm:text-sm">
          <Link href="/login" className="text-slate-300 hover:text-white">Sign in</Link>
          <Link href="/register"
            className="rounded-lg bg-[var(--aq-blue)] px-4 py-2 text-white">
            Create account
          </Link>
        </nav>
      </header>

      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-6 sm:px-8">
        <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4 text-sm">
          <div className="flex items-center gap-2 font-semibold text-cyan-200">
            <Sparkles size={16} /> Guest Chat · limited access
          </div>
          <p className="mt-2 leading-6 text-slate-300">
            Chat without an account (up to {usage} requests/hour per IP).
            Your chat is not saved. File uploads, private knowledge, history,
            and Study Abroad documents require an account.
          </p>
          <p className="mt-2 text-xs leading-5 text-slate-400">
            Privacy: your public IP address and request count are visible only
            to Aqlyra administrators for up to 24 hours for security and traffic
            monitoring. Guest messages are not saved in Aqlyra accounts.
          </p>
        </div>

        <div className="flex-1 space-y-4 py-7" aria-live="polite">
          {turns.length === 0 ? (
            <div className="mt-10 text-center">
              <h1 className="text-2xl font-semibold sm:text-3xl">
                What would you like to explore?
              </h1>
              <p className="mt-3 text-sm text-slate-400">
                Ask Aqlyra a question. Sign in to unlock files and your knowledge workspace.
              </p>
            </div>
          ) : turns.map((turn, i) => (
            <div key={i}
              className={turn.role === "user"
                ? "ml-auto max-w-[92%] rounded-2xl bg-blue-600 px-4 py-3 text-sm leading-6 text-white"
                : "max-w-[95%] whitespace-pre-wrap rounded-2xl border border-white/10 bg-[#141b2b] px-4 py-3 text-sm leading-6 text-slate-100"}>
              {turn.content}
            </div>
          ))}
        </div>

        <div className="sticky bottom-0 border-t border-white/10 bg-[#080b12] py-4">
          {error && <p role="alert" className="mb-3 text-sm text-amber-300">{error}</p>}
          <form onSubmit={submit} className="flex items-end gap-2 rounded-2xl border border-white/15 bg-[#131b2a] p-3">
            <Link href="/register" title="Sign up to upload files"
              aria-label="Sign up to upload files"
              className="flex size-10 shrink-0 items-center justify-center rounded-xl text-slate-400 hover:bg-white/10">
              <Paperclip size={19} />
            </Link>
            <label htmlFor="guest-question" className="sr-only">Ask Aqlyra</label>
            <textarea id="guest-question" rows={2} maxLength={800} required
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Ask Aqlyra anything…"
              className="max-h-32 min-h-10 min-w-0 flex-1 resize-none bg-transparent p-2 text-sm text-white outline-none placeholder:text-slate-500" />
            <button type="submit" disabled={!message.trim() || working}
              className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white disabled:opacity-40"
              aria-label="Send guest message">
              <ArrowUp size={19} />
            </button>
          </form>
          <div className="mt-3 flex items-center justify-center gap-2 text-center text-xs text-slate-400">
            <LockKeyhole size={13} />
            <span>Upload, save chats, and private RAG?</span>
            <Link href="/register" className="font-semibold text-cyan-300 hover:underline">
              Create account
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
