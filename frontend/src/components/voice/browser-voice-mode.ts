"use client";

import type { ConversationMode } from "@/types/conversation";
import type { VoiceVisualState } from "./voice-orb";

type SpeechResult = {
  isFinal: boolean;
  [index: number]: { transcript: string };
};

type SpeechEvent = {
  resultIndex: number;
  results: ArrayLike<SpeechResult>;
};

type BrowserRecognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

type SpeechWindow = Window & {
  SpeechRecognition?: new () => BrowserRecognition;
  webkitSpeechRecognition?: new () => BrowserRecognition;
};

export type BrowserVoiceController = {
  stop: () => void;
  setMuted: (muted: boolean) => void;
};

export type BrowserVoiceOptions = {
  mode: ConversationMode;
  conversationId: string | null;
  documentIds: string[];
  onConversationStarted?: (id: string) => void;
  onUserTranscript?: (text: string, isFinal: boolean) => void;
  onAgentTranscript?: (text: string, isFinal: boolean) => void;
  onState: (state: VoiceVisualState) => void;
  onError: (message: string) => void;
  onStopped: () => void;
};

export function browserSpeechIsSupported() {
  if (typeof window === "undefined") return false;
  const browser = window as SpeechWindow;
  return Boolean(
    (browser.SpeechRecognition || browser.webkitSpeechRecognition) &&
    browser.speechSynthesis &&
    typeof window.SpeechSynthesisUtterance !== "undefined",
  );
}

function speechLanguage(text: string): string {
  if (/[\u0980-\u09ff]/.test(text)) return "bn-BD";
  if (/[\u3040-\u30ff\u3400-\u9fff]/.test(text)) return "ja-JP";
  if (/[\u0900-\u097f]/.test(text)) return "hi-IN";
  return "en-US";
}

async function fetchJson(
  url: string,
  body: Record<string, unknown>,
  signal: AbortSignal,
): Promise<Record<string, unknown>> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
    signal,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || !data || typeof data !== "object") {
    const detail = data && typeof data.detail === "string"
      ? data.detail : "Voice message could not be processed.";
    throw new Error(detail);
  }
  return data as Record<string, unknown>;
}

export async function startBrowserVoiceMode(
  options: BrowserVoiceOptions,
): Promise<BrowserVoiceController> {
  if (!browserSpeechIsSupported()) {
    throw new Error(
      "Browser speech recognition is unavailable. Use text chat or a supported browser.",
    );
  }
  const browser = window as SpeechWindow;
  const SpeechRecognition = browser.SpeechRecognition || browser.webkitSpeechRecognition;
  if (!SpeechRecognition) throw new Error("Speech recognition is unavailable.");

  const controller = new AbortController();
  let conversationId = options.conversationId;
  if (!conversationId) {
    const data = await fetchJson("/api/conversations", {
      mode: options.mode,
      title: "Voice conversation",
    }, controller.signal);
    if (typeof data.id !== "string") {
      throw new Error("Unable to create a voice conversation.");
    }
    conversationId = data.id;
    options.onConversationStarted?.(conversationId);
  }

  const recognition = new SpeechRecognition();
  recognition.lang = navigator.language || "en-US";
  recognition.continuous = false;
  recognition.interimResults = true;
  let stopped = false;
  let muted = false;
  let busy = false;
  let startScheduled = false;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const stop = () => {
    if (stopped) return;
    stopped = true;
    controller.abort();
    if (timer) clearTimeout(timer);
    browser.speechSynthesis.cancel();
    recognition.onend = null;
    recognition.onresult = null;
    recognition.onerror = null;
    try { recognition.abort(); } catch { /* idle microphone */ }
    options.onStopped();
  };

  const listen = () => {
    if (stopped || muted || busy || startScheduled) return;
    startScheduled = true;
    timer = setTimeout(() => {
      startScheduled = false;
      if (stopped || muted || busy) return;
      try {
        recognition.start();
        options.onState("listening");
      } catch {
        options.onError("Unable to start microphone. Check browser permissions.");
        stop();
      }
    }, 150);
  };

  const speak = (content: string) => {
    if (stopped) return;
    const utterance = new SpeechSynthesisUtterance(content.slice(0, 3500));
    utterance.lang = speechLanguage(content);
    utterance.rate = 1;
    utterance.onend = () => {
      busy = false;
      listen();
    };
    utterance.onerror = () => {
      busy = false;
      options.onError("Voice playback unavailable; the answer remains in chat.");
      listen();
    };
    browser.speechSynthesis.speak(utterance);
    options.onState("speaking");
  };

  recognition.onresult = (event) => {
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const item = event.results[i];
      const text = item?.[0]?.transcript?.trim() || "";
      if (!text) continue;
      options.onUserTranscript?.(text, item.isFinal);
      if (!item.isFinal || busy) continue;
      busy = true;
      try { recognition.stop(); } catch { /* already ended */ }
      options.onState("thinking");
      void (async () => {
        try {
          const data = await fetchJson(
            `/api/conversations/${encodeURIComponent(conversationId!)}/messages`,
            { content: text, document_ids: options.documentIds },
            controller.signal,
          );
          if (stopped) return;
          const reply = data.assistant_message;
          const content = reply && typeof reply === "object"
            && "content" in reply && typeof reply.content === "string"
              ? reply.content : "";
          if (!content.trim()) {
            throw new Error("The AI did not return a voice response.");
          }
          options.onAgentTranscript?.(content, true);
          speak(content);
        } catch (error) {
          if (stopped) return;
          busy = false;
          options.onError(
            error instanceof Error ? error.message : "Voice response unavailable.",
          );
          listen();
        }
      })();
    }
  };
  recognition.onerror = (event) => {
    if (stopped || muted) return;
    if (event.error === "no-speech" || event.error === "aborted") return;
    options.onError(
      event.error === "not-allowed" || event.error === "service-not-allowed"
        ? "Microphone permission denied."
        : "Speech recognition interrupted; use text chat if unavailable.",
    );
    stop();
  };
  recognition.onend = listen;
  listen();
  return { stop, setMuted(nextMuted: boolean) {
    muted = nextMuted;
    if (muted) {
      try { recognition.abort(); } catch { /* already stopped */ }
      browser.speechSynthesis.cancel();
      busy = false;
      options.onState("idle");
    } else {
      listen();
    }
  } };
}
