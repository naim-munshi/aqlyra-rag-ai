"use client";

import {
  LoaderCircle,
  Mic,
  MicOff,
  PhoneOff,
} from "lucide-react";
import {
  useEffect,
  useRef,
  useState,
} from "react";
import {
  Room,
  RoomEvent,
  Track,
  createLocalAudioTrack,
  type LocalAudioTrack,
} from "livekit-client";

import {
  VoiceOrb,
  type VoiceVisualState,
} from "@/components/voice/voice-orb";
import {
  browserSpeechIsSupported,
  startBrowserVoiceMode,
  type BrowserVoiceController,
} from "@/components/voice/browser-voice-mode";
import type {
  ConversationMode,
} from "@/types/conversation";

type VoiceSessionResponse = {
  server_url: string;
  participant_token: string;
  room_name: string;
  conversation_id: string;
  mode: ConversationMode;
};

type VoiceApiError = {
  detail?: unknown;
};

type VoiceAvailability = {
  available: boolean;
  detail: string;
  requiresAuth?: boolean;
};

type VoiceCallButtonProps = {
  mode: ConversationMode;
  conversationId: string | null;
  documentIds?: string[];
  disabled?: boolean;

  onConversationStarted?: (
    conversationId: string,
  ) => void;

  onUserTranscript?: (
    text: string,
    isFinal: boolean,
  ) => void;

  onAgentTranscript?: (
    text: string,
    isFinal: boolean,
  ) => void;

  onError?: (
    message: string,
  ) => void;
};


function getApiErrorMessage(
  data: VoiceApiError | null,
) {
  if (
    data &&
    typeof data.detail === "string"
  ) {
    return data.detail;
  }

  return "Unable to start voice conversation.";
}


function normalizeAgentState(
  value: string | undefined,
): VoiceVisualState | null {
  if (
    value === "idle" ||
    value === "listening" ||
    value === "thinking" ||
    value === "speaking"
  ) {
    return value;
  }

  if (value === "initializing") {
    return "connecting";
  }

  return null;
}


function stateLabel(
  state: VoiceVisualState,
  muted: boolean,
) {
  if (muted) {
    return "Muted";
  }

  switch (state) {
    case "connecting":
      return "Connecting";
    case "thinking":
      return "Thinking";
    case "speaking":
      return "Speaking";
    case "error":
      return "Voice unavailable";
    case "idle":
    case "listening":
    default:
      return "Listening";
  }
}


function compactText(
  value: string,
  limit = 80,
) {
  const cleaned =
    value.replace(/\s+/g, " ").trim();

  if (cleaned.length <= limit) {
    return cleaned;
  }

  return `${cleaned.slice(
    0,
    limit - 1,
  )}…`;
}


export function VoiceCallButton({
  mode,
  conversationId,
  documentIds = [],
  disabled = false,
  onConversationStarted,
  onUserTranscript,
  onAgentTranscript,
  onError,
}: VoiceCallButtonProps) {
  const roomRef =
    useRef<Room | null>(null);
  const microphoneTrackRef = useRef<LocalAudioTrack | null>(null);
  const browserControllerRef = useRef<BrowserVoiceController | null>(null);
  const callAttemptRef = useRef(0);
  const startingRef = useRef(false);
  const agentEverJoinedRef = useRef(false);
  const sessionRequestControllerRef = useRef<AbortController | null>(null);
  const agentJoinTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(null);

  const audioContainerRef =
    useRef<HTMLDivElement | null>(
      null,
    );

  const [active, setActive] =
    useState(false);
  const [callTransport, setCallTransport] =
    useState<"browser" | "livekit" | null>(null);
  const [speechLocale, setSpeechLocale] = useState("auto");

  const [starting, setStarting] =
    useState(false);

  const [muted, setMuted] =
    useState(false);

  const [
    agentState,
    setAgentState,
  ] = useState<VoiceVisualState>(
    "idle",
  );

  const [
    liveUserText,
    setLiveUserText,
  ] = useState("");

  const [
    liveAgentText,
    setLiveAgentText,
  ] = useState("");

  const [error, setError] =
    useState("");

  const [availability, setAvailability] =
    useState<VoiceAvailability | null>(null);

  const [needsAudioUnlock, setNeedsAudioUnlock] =
    useState(false);

  async function refreshVoiceAvailability(signal?: AbortSignal) {
    try {
      const response = await fetch("/api/voice/status", {
        cache: "no-store",
        signal,
      });
      if (response.status === 401) {
        if (!signal?.aborted) setAvailability({
          available: false,
          detail: "Sign in to use voice calls.",
          requiresAuth: true,
        });
        return;
      }
      if (!response.ok) throw new Error("Voice status unavailable");
      const data = (await response.json()) as VoiceAvailability;
      if (typeof data.available !== "boolean") {
        throw new Error("Invalid voice status");
      }
      if (!signal?.aborted) {
        setAvailability(data);
        if (data.available) setError("");
      }
    } catch {
      if (!signal?.aborted) {
        setAvailability({
          available: false,
          detail: "Voice calling is temporarily unavailable. Please use text chat.",
        });
      }
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/voice/status", {
      cache: "no-store",
      signal: controller.signal,
    }).then(async response => {
      if (response.status === 401) {
        if (!controller.signal.aborted) setAvailability({
          available: false,
          detail: "Sign in to use voice calls.",
          requiresAuth: true,
        });
        return;
      }
      if (!response.ok) throw new Error("Voice status unavailable");
      const data = (await response.json()) as VoiceAvailability;
      if (typeof data.available !== "boolean") {
        throw new Error("Invalid voice status");
      }
      if (!controller.signal.aborted) setAvailability(data);
    }).catch(() => {
      if (!controller.signal.aborted) {
        setAvailability({
          available: false,
          detail: "Voice calling is temporarily unavailable. Please use text chat.",
        });
      }
    });
    return () => controller.abort();
  }, []);


  function clearAgentJoinTimer() {
    if (agentJoinTimerRef.current !== null) {
      clearTimeout(agentJoinTimerRef.current);
      agentJoinTimerRef.current = null;
    }
  }

  function hasVoiceAgent(room: Room): boolean {
    return Array.from(room.remoteParticipants.values()).some(
      (participant) =>
        participant.isAgent &&
        !participant.attributes["lk.publish_on_behalf"],
    );
  }

  function waitForAgent(room: Room) {
    clearAgentJoinTimer();
    if (hasVoiceAgent(room)) {
      agentEverJoinedRef.current = true;
      setError("");
      setAgentState((current) =>
        current === "connecting" || current === "error"
          ? "listening" : current,
      );
      return;
    }
    setAgentState("connecting");
    agentJoinTimerRef.current = setTimeout(() => {
      agentJoinTimerRef.current = null;
      if (
        roomRef.current !== room ||
        hasVoiceAgent(room)
      ) return;
      const message = "Real-time voice could not connect to Aqlyra. Please try again or use text chat.";
      roomRef.current = null;
      stopMicrophoneTrack();
      void room.disconnect().catch(() => {
        // The microphone is already released; teardown is best effort.
      });
      clearAudioElements();
      setActive(false);
      setStarting(false);
      setAgentState("error");
      setError(message);
      onError?.(message);
    }, 45000); // Free LiveKit Cloud agents can cold-start before joining.
  }

  function stopMicrophoneTrack() {
    microphoneTrackRef.current?.stop();
    microphoneTrackRef.current = null;
  }

  function clearAudioElements() {
    const container =
      audioContainerRef.current;

    if (!container) {
      return;
    }

    container
      .querySelectorAll("audio")
      .forEach((element) => {
        element.remove();
      });
  }


  async function endCall() {
    callAttemptRef.current += 1;
    sessionRequestControllerRef.current?.abort();
    sessionRequestControllerRef.current = null;
    startingRef.current = false;
    clearAgentJoinTimer();
    const room =
      roomRef.current;

    roomRef.current = null;
    browserControllerRef.current?.stop();
    browserControllerRef.current = null;

    // Release the device immediately, even if network teardown stalls.
    stopMicrophoneTrack();
    clearAudioElements();
    if (room) {
      void room.disconnect().catch(() => {
        // Local tracks are already stopped; disconnect is best effort.
      });
    }

    setActive(false);
    setStarting(false);
    setCallTransport(null);
    setMuted(false);
    setAgentState("idle");
    setLiveUserText("");
    setLiveAgentText("");
    setNeedsAudioUnlock(false);
    setError("");
  }



  function startFreeBrowserCall() {
    if (disabled || active || starting || startingRef.current) return;
    if (availability?.requiresAuth) {
      const message = "Sign in to use voice calls.";
      setError(message);
      onError?.(message);
      return;
    }
    // Browser speech is opt-in, not a silent downgrade of LiveKit RTC.
    // Its recognition runs in the user's browser and may be processed by
    // the browser vendor. AI text turns still use the authenticated API.
    if (!browserSpeechIsSupported()) {
      const message =
        "Free Browser Voice is not supported on this browser. Try Safari or Chrome with microphone permission, or use text chat.";
      setError(message);
      onError?.(message);
      return;
    }

    const attempt = ++callAttemptRef.current;
    startingRef.current = true;
    setCallTransport("browser");
    setStarting(true);
    setActive(true);
    setMuted(false);
    setNeedsAudioUnlock(false);
    setError("");
    setLiveUserText("");
    setLiveAgentText("");
    setAgentState("connecting");

    // startBrowserVoiceMode installs recognition synchronously before
    // resolving, preserving the direct-tap microphone permission on iOS.
    void startBrowserVoiceMode({
      mode,
      conversationId,
      documentIds,
      speechLocale,
      onConversationStarted: id => {
        if (callAttemptRef.current !== attempt) return;
        onConversationStarted?.(id);
      },
      onUserTranscript: (text, isFinal) => {
        if (callAttemptRef.current !== attempt) return;
        setLiveUserText(text);
        onUserTranscript?.(text, isFinal);
      },
      onAgentTranscript: (text, isFinal) => {
        if (callAttemptRef.current !== attempt) return;
        setLiveAgentText(text);
        onAgentTranscript?.(text, isFinal);
      },
      onState: state => {
        if (callAttemptRef.current === attempt) setAgentState(state);
      },
      onError: message => {
        if (callAttemptRef.current !== attempt) return;
        setError(message);
        onError?.(message);
      },
      onAudioBlocked: () => {
        if (callAttemptRef.current === attempt) setNeedsAudioUnlock(true);
      },
      onAudioStarted: () => {
        if (callAttemptRef.current === attempt) setNeedsAudioUnlock(false);
      },
      onStopped: () => {
        if (callAttemptRef.current !== attempt) return;
        callAttemptRef.current += 1;
        browserControllerRef.current = null;
        startingRef.current = false;
        setActive(false);
        setStarting(false);
        setCallTransport(null);
        setNeedsAudioUnlock(false);
        setMuted(false);
      },
    }).then(browserController => {
      if (callAttemptRef.current !== attempt) {
        browserController.stop();
        return;
      }
      browserControllerRef.current = browserController;
      startingRef.current = false;
      setStarting(false);
    }).catch(startError => {
      if (callAttemptRef.current !== attempt) return;
      startingRef.current = false;
      setStarting(false);
      setActive(false);
      setCallTransport(null);
      setAgentState("error");
      const message = startError instanceof Error
        ? startError.message : "Unable to start Browser Voice.";
      setError(message);
      onError?.(message);
    });
  }

  async function startCall() {
    if (
      disabled ||
      active ||
      starting ||
      startingRef.current
    ) {
      return;
    }

    // Never silently downgrade full-duplex voice to browser speech/TTS.
    // That fallback cannot hear interruption while speaking on mobile.
    if (!availability?.available) {
      const message = availability?.detail ||
        "Aqlyra real-time voice is unavailable. Sign in or retry."; 
      setError(message);
      onError?.(message);
      return;
    }

    clearAgentJoinTimer();
    startingRef.current = true;
    agentEverJoinedRef.current = false;
    const attempt = ++callAttemptRef.current;
    setCallTransport("livekit");
    setStarting(true);
    setError("");
    setLiveUserText("");
    setLiveAgentText("");
    setAgentState("connecting");

    let room: Room | null = null;
    let microphoneTrack: LocalAudioTrack | null = null;

    try {
      // Acquire the actual LiveKit track on the direct iOS Safari tap.
      // Do not stop it and re-request capture after network awaits: Safari
      // may reject a second getUserMedia outside user activation.
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("This browser does not support microphone calls.");
      }
      microphoneTrack = await createLocalAudioTrack({
        echoCancellation: true,
        noiseSuppression: true,
      });
      if (callAttemptRef.current !== attempt) {
        throw new DOMException("Call ended", "AbortError");
      }
      microphoneTrackRef.current = microphoneTrack;

      // Bound backend waiting time so a stalled network cannot hold the
      // microphone indefinitely. End Call and unmount abort the request.
      const requestController = new AbortController();
      sessionRequestControllerRef.current = requestController;
      const timeoutId = setTimeout(() => requestController.abort(), 15000);
      let response: Response;
      try {
        response = await fetch("/api/voice/session", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            mode,
            ...(conversationId ? { conversation_id: conversationId } : {}),
            title: "Voice conversation",
            document_ids: documentIds,
          }),
          signal: requestController.signal,
        });
      } finally {
        clearTimeout(timeoutId);
        if (sessionRequestControllerRef.current === requestController) {
          sessionRequestControllerRef.current = null;
        }
      }

      const data =
        (await response.json()) as
          | VoiceSessionResponse
          | VoiceApiError;

      if (response.status === 429) {
        // Retrying repeatedly can only deepen the per-user voice limit.
        // Preserve the backend's Retry-After without silently restarting.
        const retry = Number(response.headers.get("Retry-After"));
        throw new Error(
          Number.isFinite(retry) && retry > 0
            ? `Too many voice reconnect attempts. Retry in ${Math.ceil(retry)} seconds.`
            : "Too many voice reconnect attempts. Try again shortly.",
        );
      }
      if (
        !response.ok ||
        !(
          "participant_token" in
          data
        )
      ) {
        throw new Error(
          getApiErrorMessage(
            data as VoiceApiError,
          ),
        );
      }

      if (callAttemptRef.current !== attempt) {
        throw new DOMException("Call ended", "AbortError");
      }
      const session =
        data as VoiceSessionResponse;

      room = new Room({
        adaptiveStream: true,
        dynacast: true,
      });

      roomRef.current = room;

      room.registerTextStreamHandler(
        "lk.transcription",
        async (
          reader,
          participantInfo,
        ) => {
          const text =
            (
              await reader.readAll()
            ).trim();

          if (!text) {
            return;
          }

          const attributes =
            reader.info.attributes ?? {};

          if (
            !attributes[
              "lk.transcribed_track_id"
            ]
          ) {
            return;
          }

          const isFinal =
            String(
              attributes[
                "lk.transcription_final"
              ] ?? "",
            ).toLowerCase() ===
            "true";

          const isLocalUser =
            participantInfo.identity ===
            room?.localParticipant
              .identity;

          if (isLocalUser) {
            setLiveUserText(text);

            onUserTranscript?.(
              text,
              isFinal,
            );

            return;
          }

          setLiveAgentText(text);

          onAgentTranscript?.(
            text,
            isFinal,
          );
        },
      );

      room.on(RoomEvent.AudioPlaybackStatusChanged, () => {
        if (roomRef.current === room) {
          setNeedsAudioUnlock(!room!.canPlaybackAudio);
        }
      });

      room.on(
        RoomEvent.TrackSubscribed,
        (track) => {
          if (
            track.kind !==
            Track.Kind.Audio
          ) {
            return;
          }

          const element =
            track.attach();

          element.autoplay = true;
          element.muted = false;

          audioContainerRef
            .current
            ?.appendChild(element);
          if (room && !room.canPlaybackAudio) {
            setNeedsAudioUnlock(true);
          }
        },
      );

      room.on(
        RoomEvent.TrackUnsubscribed,
        (track) => {
          track.detach().forEach(
            (element) => {
              element.remove();
            },
          );
        },
      );

      room.on(
        RoomEvent.ParticipantConnected,
        (participant) => {
          if (
            !participant.isAgent ||
            participant.attributes["lk.publish_on_behalf"]
          ) return;
          clearAgentJoinTimer();
          agentEverJoinedRef.current = true;
          setError("");
          const state =
            normalizeAgentState(
              participant.attributes[
                "lk.agent.state"
              ],
            );

          setAgentState(
            state ?? "listening",
          );
        },
      );

      room.on(
        RoomEvent
          .ParticipantAttributesChanged,
        (
          changedAttributes,
          participant,
        ) => {
          if (
            participant === room?.localParticipant ||
            !participant.isAgent ||
            participant.attributes["lk.publish_on_behalf"]
          ) {
            return;
          }

          const state =
            normalizeAgentState(
              changedAttributes[
                "lk.agent.state"
              ],
            );

          if (state) {
            setAgentState(state);
          }
        },
      );

      room.on(RoomEvent.ParticipantDisconnected, () => {
        if (
          room !== null &&
          roomRef.current === room &&
          !hasVoiceAgent(room)
        ) {
          waitForAgent(room);
        }
      });

      room.on(
        RoomEvent.Disconnected,
        () => {
          // Unexpected RTC drops must never look like a user-initiated
          // hangup. endCall and unmount clear roomRef before disconnect.
          if (roomRef.current !== room) return;
          clearAgentJoinTimer();
          roomRef.current = null;

          stopMicrophoneTrack();
          clearAudioElements();

          const message = agentEverJoinedRef.current
            ? "Voice call disconnected unexpectedly. Check your connection and try again."
            : "LiveKit disconnected before the AI agent joined. Please check the voice connection and try again.";
          setActive(false);
          setStarting(false);
          setMuted(false);
          setNeedsAudioUnlock(false);
          setAgentState("error");
          setError(message);
          onError?.(message);
        },
      );

      await room.connect(
        session.server_url,
        session.participant_token,
      );
      if (callAttemptRef.current !== attempt || roomRef.current !== room) {
        throw new DOMException("Call ended", "AbortError");
      }
      // Publish the track acquired on the original user gesture. No
      // second microphone permission request after the network roundtrip.
      await room.localParticipant.publishTrack(microphoneTrack, {
        source: Track.Source.Microphone,
      });
      if (callAttemptRef.current !== attempt || roomRef.current !== room) {
        throw new DOMException("Call ended", "AbortError");
      }

      onConversationStarted?.(
        session.conversation_id,
      );

      setMuted(false);
      setActive(true);
      startingRef.current = false;
      setStarting(false);
      setNeedsAudioUnlock(!room.canPlaybackAudio);

      waitForAgent(room);
    } catch (startError) {
      clearAgentJoinTimer();
      if (room) {
        try {
          await room.disconnect();
        } catch {
          // Best-effort cleanup.
        }
      }

      if (microphoneTrack) {
        microphoneTrack.stop();
        if (microphoneTrackRef.current === microphoneTrack) {
          microphoneTrackRef.current = null;
        }
      }
      if (roomRef.current === room) roomRef.current = null;
      if (callAttemptRef.current !== attempt) return;

      startingRef.current = false;
      clearAudioElements();

      const message =
        startError instanceof DOMException &&
        (startError.name === "NotAllowedError" ||
         startError.name === "PermissionDeniedError")
          ? "Microphone access was denied. Allow the microphone in Safari or browser settings and retry."
          : startError instanceof DOMException &&
            startError.name === "AbortError"
            ? "The voice connection timed out or was cancelled. Please retry."
            : startError instanceof Error
              ? startError.message
              : "Unable to start voice conversation.";

      setError(message);
      setAgentState("error");
      setStarting(false);
      setActive(false);
      setCallTransport(null);
      setNeedsAudioUnlock(false);

      onError?.(message);
    }
  }


  async function enableAudio() {
    if (callTransport === "browser") {
      // Must execute synchronously on the button tap for iOS speech audio.
      if (browserControllerRef.current?.retryAudio()) {
        setNeedsAudioUnlock(false);
        setError("");
      } else {
        setError("There is no speech to replay yet. Try speaking again.");
      }
      return;
    }
    const room = roomRef.current;
    if (!room) return;
    try {
      // Must run directly from the user's click on iOS Safari.
      await room.startAudio();
      setNeedsAudioUnlock(!room.canPlaybackAudio);
      setError("");
    } catch {
      setNeedsAudioUnlock(true);
      setError("Tap Enable sound again or allow audio playback in your browser.");
    }
  }

  async function toggleMute() {
    if (callTransport === "browser") {
      const nextMuted = !muted;
      browserControllerRef.current?.setMuted(nextMuted);
      setMuted(nextMuted);
      return;
    }
    const room =
      roomRef.current;

    if (!room) {
      return;
    }

    const nextMuted = !muted;

    try {
      await room.localParticipant
        .setMicrophoneEnabled(
          !nextMuted,
        );

      setMuted(nextMuted);
    } catch (muteError) {
      const message =
        muteError instanceof Error
          ? muteError.message
          : "Unable to change microphone state.";

      setError(message);

      onError?.(message);
    }
  }


  useEffect(() => {
    return () => {
      callAttemptRef.current += 1;
      sessionRequestControllerRef.current?.abort();
      sessionRequestControllerRef.current = null;
      startingRef.current = false;
      clearAgentJoinTimer();
      browserControllerRef.current?.stop();
      browserControllerRef.current = null;
      stopMicrophoneTrack();
      const room =
        roomRef.current;

      roomRef.current = null;

      if (room) {
        void room.disconnect().catch(() => {
          // Navigation must not leave an unhandled WebRTC teardown error.
        });
      }
    };
  }, []);


  if (!active && !starting) {
    return (
      <>
        <button
          type="button"
          disabled={disabled}
          aria-label="Start free browser voice conversation"
          title="Free Browser Voice · no separate voice server · supported browsers only"
          onClick={startFreeBrowserCall}
          className="group relative flex h-10 w-10 items-center justify-center rounded-full border border-[var(--aq-border)] bg-[var(--aq-card)] text-[var(--aq-muted)] transition hover:border-[var(--aq-cyan)]/60 hover:text-[var(--aq-cyan)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <span className="absolute inset-1 rounded-full transition group-hover:shadow-[0_0_18px_rgba(34,211,238,0.22)]" />

          <Mic
            size={18}
            className="relative z-10"
          />
        </button>

        {availability?.available && (
          <button
            type="button"
            disabled={disabled}
            aria-label="Start LiveKit real-time voice"
            title="LiveKit real-time voice requires an online hosted agent"
            onClick={() => { void startCall(); }}
            className="rounded-full border border-[var(--aq-border)] px-2 py-1 text-[10px] font-medium text-[var(--aq-muted)] hover:text-[var(--aq-cyan)] disabled:opacity-50"
          >
            LiveKit
          </button>
        )}

        {error && (
          <div
            role="alert"
            className="absolute bottom-[calc(100%+8px)] right-0 z-40 w-[min(300px,calc(100vw-24px))] rounded-xl border border-red-500/30 bg-[var(--aq-panel)] p-3 text-xs leading-5 text-[var(--aq-text)] shadow-xl"
          >
            {error}
            {availability?.available === false && (
              <button
                type="button"
                onClick={() => { void refreshVoiceAvailability(); }}
                className="ml-2 font-semibold text-[var(--aq-cyan)] underline"
              >
                Check voice availability again
              </button>
            )}
            <button
              type="button"
              onClick={() => setError("")}
              className="ml-2 font-semibold text-[var(--aq-cyan)] underline"
            >
              Dismiss
            </button>
          </div>
        )}
        <div ref={audioContainerRef} className="hidden" />
      </>
    );
  }


  return (
    <>
      <div className="absolute bottom-[72px] right-2 z-40 w-[min(300px,calc(100vw-24px))] overflow-hidden rounded-[24px] border border-[var(--aq-border)] bg-[var(--aq-card)]/95 p-4 shadow-2xl backdrop-blur-xl">
        <div className="flex flex-col items-center">
          <VoiceOrb
            state={
              starting
                ? "connecting"
                : agentState
            }
            muted={muted}
          />

          <div className="-mt-1 text-center">
            <div className="text-sm font-semibold text-[var(--aq-text)]">
              {callTransport === "browser"
                ? "Aqlyra · Free Browser Voice"
                : "Aqlyra Voice"}
            </div>

            <div className="mt-0.5 flex items-center justify-center gap-1.5 text-[11px] text-[var(--aq-muted)]">
              <span
                className={[
                  "h-1.5 w-1.5 rounded-full",
                  muted
                    ? "bg-[var(--aq-muted)]"
                    : agentState ===
                        "speaking"
                      ? "animate-pulse bg-[var(--aq-cyan)]"
                      : "animate-pulse bg-[var(--aq-blue)]",
                ].join(" ")}
              />

              {stateLabel(
                starting
                  ? "connecting"
                  : agentState,
                muted,
              )}
            </div>
          </div>

          {callTransport === "browser" && (
            <p className="mt-3 text-center text-[10px] leading-4 text-[var(--aq-muted)]">
              Free turn-based voice uses your browser&apos;s speech service;
              audio recognition may be processed by the browser provider.
              Normal Aqlyra AI chat quotas still apply.
            </p>
          )}

          <div className="mt-4 w-full space-y-1.5">
            {liveUserText ? (
              <div className="flex gap-2 text-[11px] leading-4">
                <span className="shrink-0 font-semibold text-[var(--aq-blue)]">
                  You
                </span>

                <span className="min-w-0 text-[var(--aq-muted)]">
                  {compactText(
                    liveUserText,
                  )}
                </span>
              </div>
            ) : null}

            {liveAgentText ? (
              <div className="flex gap-2 text-[11px] leading-4">
                <span className="shrink-0 font-semibold text-[var(--aq-cyan)]">
                  AI
                </span>

                <span className="min-w-0 text-[var(--aq-text)]">
                  {compactText(
                    liveAgentText,
                  )}
                </span>
              </div>
            ) : null}

            {!liveUserText &&
            !liveAgentText ? (
              <div className="text-center text-[11px] text-[var(--aq-muted)]">
                {agentState === "connecting"
                  ? "Waiting for the AI voice agent to join..."
                  : agentState === "error"
                    ? "The AI voice agent is unavailable."
                    : callTransport === "browser"
                     ? "Take turns speaking. Browser Voice cannot hear interruptions during playback."
                     : "Speak naturally. Aqlyra is listening."}
              </div>
            ) : null}
          </div>

          {error ? (
            <div role="alert" className="mt-3 w-full rounded-xl border border-red-500/20 bg-red-500/5 px-3 py-2 text-[11px] text-red-500">
              {error}
            </div>
          ) : null}

          {needsAudioUnlock && (
            <button
              type="button"
              onClick={() => { void enableAudio(); }}
              className="mt-3 min-h-11 w-full rounded-xl bg-[var(--aq-blue)] px-3 text-xs font-semibold text-white"
            >
              Enable sound
            </button>
          )}

          {callTransport === "browser" && (
            <div className="mt-3 flex w-full flex-wrap items-center justify-center gap-2">
              <label htmlFor="browser-voice-locale" className="text-[11px] text-[var(--aq-muted)]">
                Listen in
              </label>
              <select
                id="browser-voice-locale"
                value={speechLocale}
                onChange={event => {
                  const locale = event.target.value;
                  setSpeechLocale(locale);
                  browserControllerRef.current?.setSpeechLocale(locale);
                }}
                className="rounded-lg border border-[var(--aq-border)] bg-[var(--aq-control)] px-2 py-1 text-xs text-[var(--aq-text)]"
              >
                <option value="auto">Device language</option>
                <option value="en-US">English</option>
                <option value="bn-BD">বাংলা</option>
                <option value="ja-JP">日本語</option>
                <option value="hi-IN">हिन्दी</option>
              </select>
              {agentState === "speaking" && (
                <button
                  type="button"
                  onClick={() => { browserControllerRef.current?.interruptSpeech(); }}
                  className="rounded-lg border border-[var(--aq-border)] px-2 py-1 text-xs font-semibold text-[var(--aq-cyan)]"
                >
                  Stop reply
                </button>
              )}
            </div>
          )}

          <div className="mt-4 flex items-center justify-center gap-3">
            <button
              type="button"
              disabled={starting}
              aria-label={
                muted
                  ? "Unmute microphone"
                  : "Mute microphone"
              }
              title={
                muted
                  ? "Unmute"
                  : "Mute"
              }
              onClick={() => {
                void toggleMute();
              }}
              className="flex h-11 w-11 items-center justify-center rounded-full border border-[var(--aq-border)] bg-[var(--aq-control)] text-[var(--aq-text)] transition hover:border-[var(--aq-cyan)]/50 hover:text-[var(--aq-cyan)] disabled:opacity-50"
            >
              {muted ? (
                <MicOff size={18} />
              ) : (
                <Mic size={18} />
              )}
            </button>

            <button
              type="button"
              aria-label="End voice conversation"
              title="End call"
              onClick={() => {
                void endCall();
              }}
              className="flex h-11 w-11 items-center justify-center rounded-full bg-red-500 text-white shadow-lg transition hover:scale-105 hover:bg-red-600"
            >
              <PhoneOff size={18} />
            </button>
          </div>
        </div>
      </div>

      <button
        type="button"
        disabled
        aria-label="Voice conversation active"
        className="relative flex h-10 w-10 items-center justify-center rounded-full border border-[var(--aq-cyan)]/60 bg-[var(--aq-control)] text-[var(--aq-cyan)] shadow-[0_0_18px_rgba(34,211,238,0.16)]"
      >
        {starting ? (
          <LoaderCircle
            size={18}
            className="animate-spin"
          />
        ) : muted ? (
          <MicOff size={18} />
        ) : (
          <Mic
            size={18}
            className={
              agentState === "speaking"
                ? "animate-pulse"
                : ""
            }
          />
        )}
      </button>

      <div
        ref={audioContainerRef}
        className="hidden"
      />
    </>
  );
}
