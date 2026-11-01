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
  // Must be invoked directly from the user's audio-unlock click on iOS.
  retryAudio: () => boolean;
};

export type BrowserVoiceOptions = {
  mode: ConversationMode;
  conversationId: string | null;
  documentIds: string[];
  speechLocale?: string;
  onConversationStarted?: (id: string) => void;
  onUserTranscript?: (text: string, isFinal: boolean) => void;
  onAgentTranscript?: (text: string, isFinal: boolean) => void;
  onState: (state: VoiceVisualState) => void;
  onError: (message: string) => void;
  onAudioBlocked?: () => void;
  onAudioStarted?: () => void;
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
  // Set up speech recognition before any network await. On iOS Safari,
  // the first microphone activation must remain in the actual user tap.
  // Conversation creation may finish while speech is being recognized.
  const recognition = new SpeechRecognition();
  recognition.lang = options.speechLocale && options.speechLocale !== "auto"
    ? options.speechLocale : (navigator.language || "en-US");
  recognition.continuous = false;
  recognition.interimResults = true;
  let stopped = false;
  let muted = false;
  let busy = false;
  let processing = false;
  let startScheduled = false;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let playbackTimer: ReturnType<typeof setTimeout> | null = null;
  let playing: SpeechSynthesisUtterance | null = null;
  let lastReply = "";

  const clearPlaybackTimer = () => {
    if (playbackTimer !== null) clearTimeout(playbackTimer);
    playbackTimer = null;
  };

  const stop = () => {
    if (stopped) return;
    stopped = true;
    controller.abort();
    if (timer) clearTimeout(timer);
    clearPlaybackTimer();
    playing = null;
    browser.speechSynthesis.cancel();
    recognition.onend = null;
    recognition.onresult = null;
    recognition.onerror = null;
    try { recognition.abort(); } catch { /* idle microphone */ }
    options.onStopped();
  };

  const beginRecognition = () => {
    if (stopped || muted || busy) return;
    try {
      recognition.start();
      options.onState("listening");
    } catch {
      options.onError("Unable to start microphone. Check browser permissions.");
      stop();
    }
  };

  const listen = (immediate = false) => {
    if (stopped || muted || busy || startScheduled) return;
    if (immediate) {
      beginRecognition();
      return;
    }
    startScheduled = true;
    timer = setTimeout(() => {
      startScheduled = false;
      beginRecognition();
    }, 150);
  };

  const speak = (content: string) => {
    if (stopped || muted) return;
    // Keep long responses in chat; speaking the first segment prevents an
    // endless mobile TTS session and gives the user an audible reply.
    const utterance = new SpeechSynthesisUtterance(content.slice(0, 1400));
    utterance.lang = speechLanguage(content);
    utterance.rate = 1;
    const failPlayback = (message: string) => {
      if (stopped || playing !== utterance) return;
      playing = null;
      clearPlaybackTimer();
      busy = false;
      options.onError(message);
      options.onAudioBlocked?.();
      listen();
    };
    utterance.onstart = () => {
      if (stopped || playing !== utterance) return;
      clearPlaybackTimer();
      options.onAudioStarted?.();
      options.onState("speaking");
      playbackTimer = setTimeout(() => {
        if (playing !== utterance) return;
        playing = null;
        clearPlaybackTimer();
        browser.speechSynthesis.cancel();
        busy = false;
        options.onError("Audio playback stalled; the full answer remains in chat.");
        options.onAudioBlocked?.();
        listen();
      }, 165000);
    };
    utterance.onend = () => {
      if (stopped || playing !== utterance) return;
      playing = null;
      clearPlaybackTimer();
      busy = false;
      listen();
    };
    utterance.onerror = () => {
      // Browser TTS often reports an error when muted/cancelled intentionally.
      if (stopped || muted || playing !== utterance) return;
      failPlayback("Voice playback unavailable; the answer remains in chat.");
    };
    playing = utterance;
    // iOS Safari can accept speak() without actually starting sound.
    // Recover listening after a bounded start timeout rather than hanging.
    playbackTimer = setTimeout(() => {
      if (stopped || playing !== utterance) return;
      playing = null;
      clearPlaybackTimer();
      browser.speechSynthesis.cancel();
      busy = false;
      options.onError("Voice audio did not start. Tap to hear the reply or check your browser audio permissions.");
      options.onAudioBlocked?.();
      listen();
    }, 12000);
    try {
      browser.speechSynthesis.speak(utterance);
    } catch {
      failPlayback("Voice playback unavailable; the answer remains in chat.");
    }
  };

  const conversationReady: Promise<string> = conversationId
    ? Promise.resolve(conversationId)
    : fetchJson("/api/conversations", {
      mode: options.mode,
      title: "Voice conversation",
    }, controller.signal).then((data) => {
      if (typeof data.id !== "string" || !data.id) {
        throw new Error("Unable to create a voice conversation.");
      }
      conversationId = data.id;
      if (!stopped) options.onConversationStarted?.(conversationId);
      return conversationId;
    });
  // Install a rejection observer even if no speech event arrives.
  void conversationReady.catch((error) => {
    if (stopped) return;
    options.onError(
      error instanceof Error ? error.message : "Unable to create voice conversation.",
    );
    stop();
  });

  recognition.onresult = (event) => {
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const item = event.results[i];
      const text = item?.[0]?.transcript?.trim() || "";
      if (!text) continue;
      options.onUserTranscript?.(text, item.isFinal);
      if (!item.isFinal || busy) continue;
      busy = true;
      processing = true;
      try { recognition.stop(); } catch { /* already ended */ }
      options.onState("thinking");
      void (async () => {
        try {
          const activeConversationId = await conversationReady;
          if (stopped) return;
          const data = await fetchJson(
            `/api/conversations/${encodeURIComponent(activeConversationId)}/messages`,
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
          lastReply = content;
          if (!muted) speak(content);
        } catch (error) {
          if (stopped) return;
          busy = false;
          options.onError(
            error instanceof Error ? error.message : "Voice response unavailable.",
          );
          listen();
        } finally {
          processing = false;
          if (!stopped && muted) {
            busy = false;
            options.onState("idle");
          }
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
  listen(true); // First call must be inside the user's direct click event.
  return { stop, retryAudio() {
    // This method runs synchronously in the click handler, before any await.
    if (stopped || muted || processing || !lastReply.trim()) return false;
    if (timer) clearTimeout(timer);
    timer = null;
    startScheduled = false;
    busy = true;
    try { recognition.abort(); } catch { /* already idle */ }
    playing = null;
    clearPlaybackTimer();
    browser.speechSynthesis.cancel();
    speak(lastReply);
    return true;
  }, setMuted(nextMuted: boolean) {
    muted = nextMuted;
    if (muted) {
      try { recognition.abort(); } catch { /* already stopped */ }
      playing = null;
      clearPlaybackTimer();
      browser.speechSynthesis.cancel();
      // Keep the outstanding AI turn serialized until its fetch finishes.
      // Otherwise unmuting can capture a second turn and race the first.
      busy = processing;
      options.onState("idle");
    } else {
      listen();
    }
  } };
}
