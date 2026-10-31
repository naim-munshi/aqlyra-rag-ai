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
import type {
  ConversationMode,
} from "@/types/conversation";
import {
  browserSpeechIsSupported,
  startBrowserVoiceMode,
  type BrowserVoiceController,
} from "@/components/voice/browser-voice-mode";


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
  const browserVoiceRef = useRef<BrowserVoiceController | null>(null);
  const [browserMode, setBrowserMode] = useState(false);
  const microphoneTrackRef = useRef<LocalAudioTrack | null>(null);
  const callAttemptRef = useRef(0);
  const startingRef = useRef(false);
  const sessionRequestControllerRef = useRef<AbortController | null>(null);
  const agentJoinTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(null);

  const audioContainerRef =
    useRef<HTMLDivElement | null>(
      null,
    );

  const [active, setActive] =
    useState(false);

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
      const message =
        "The AI voice agent did not join. The call was ended. " +
        "Please retry once the voice service is online.";
      roomRef.current = null;
      stopMicrophoneTrack();
      void room.disconnect();
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
    browserVoiceRef.current?.stop();
    browserVoiceRef.current = null;
    setBrowserMode(false);
    callAttemptRef.current += 1;
    sessionRequestControllerRef.current?.abort();
    sessionRequestControllerRef.current = null;
    startingRef.current = false;
    clearAgentJoinTimer();
    const room =
      roomRef.current;

    roomRef.current = null;

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
    setMuted(false);
    setAgentState("idle");
    setLiveUserText("");
    setLiveAgentText("");
    setNeedsAudioUnlock(false);
    setError("");
  }


  async function startBrowserSpeech() {
    if (!browserSpeechIsSupported()) {
      const message = "Browser speech recognition is not supported on this device.";
      setError(message);
      onError?.(message);
      return;
    }
    clearAgentJoinTimer();
    startingRef.current = true;
    const attempt = ++callAttemptRef.current;
    setStarting(true);
    setError("");
    setLiveUserText("");
    setLiveAgentText("");
    setAgentState("connecting");
    try {
      const controller = await startBrowserVoiceMode({
        mode,
        conversationId,
        documentIds,
        onConversationStarted,
        onUserTranscript: (text, isFinal) => {
          setLiveUserText(text);
          onUserTranscript?.(text, isFinal);
        },
        onAgentTranscript: (text, isFinal) => {
          setLiveAgentText(text);
          onAgentTranscript?.(text, isFinal);
        },
        onState: setAgentState,
        onError: (message) => {
          setError(message);
          onError?.(message);
        },
        onStopped: () => {
          browserVoiceRef.current = null;
          setBrowserMode(false);
          setActive(false);
          setStarting(false);
          startingRef.current = false;
          setAgentState("idle");
        },
      });
      if (callAttemptRef.current !== attempt) {
        controller.stop();
        return;
      }
      browserVoiceRef.current = controller;
      startingRef.current = false;
      setBrowserMode(true);
      setMuted(false);
      setActive(true);
      setStarting(false);
    } catch (error) {
      if (callAttemptRef.current !== attempt) return;
      startingRef.current = false;
      const message = error instanceof Error
        ? error.message : "Browser speech mode is unavailable.";
      setError(message);
      setAgentState("error");
      setStarting(false);
      onError?.(message);
    }
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

    if (!availability?.available) {
      if (availability?.available === false && browserSpeechIsSupported()) {
        // Start public browser speech mode only from the explicit user click.
        void startBrowserSpeech();
        return;
      }
      const message = availability?.detail ??
        "Checking voice availability. Please try again shortly.";
      setError(message);
      onError?.(message);
      return;
    }

    clearAgentJoinTimer();
    startingRef.current = true;
    const attempt = ++callAttemptRef.current;
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
          if (roomRef.current !== room) return;
          clearAgentJoinTimer();
          roomRef.current = null;

          stopMicrophoneTrack();
          clearAudioElements();

          setActive(false);
          setStarting(false);
          setMuted(false);
          setNeedsAudioUnlock(false);
          setAgentState("idle");
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
      setNeedsAudioUnlock(false);

      onError?.(message);
    }
  }


  async function enableAudio() {
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
    if (browserVoiceRef.current) {
      const next = !muted;
      browserVoiceRef.current.setMuted(next);
      setMuted(next);
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
      browserVoiceRef.current?.stop();
      browserVoiceRef.current = null;
      callAttemptRef.current += 1;
      sessionRequestControllerRef.current?.abort();
      sessionRequestControllerRef.current = null;
      startingRef.current = false;
      clearAgentJoinTimer();
      stopMicrophoneTrack();
      const room =
        roomRef.current;

      roomRef.current = null;

      if (room) {
        void room.disconnect();
      }
    };
  }, []);


  if (!active && !starting) {
    return (
      <>
        <button
          type="button"
          disabled={disabled}
          aria-label="Start voice conversation"
          title={availability?.available === false ? "Voice service unavailable" : "Start voice conversation"}
          onClick={() => {
            void startCall();
          }}
          className="group relative flex h-10 w-10 items-center justify-center rounded-full border border-[var(--aq-border)] bg-[var(--aq-card)] text-[var(--aq-muted)] transition hover:border-[var(--aq-cyan)]/60 hover:text-[var(--aq-cyan)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <span className="absolute inset-1 rounded-full transition group-hover:shadow-[0_0_18px_rgba(34,211,238,0.22)]" />

          <Mic
            size={18}
            className="relative z-10"
          />
        </button>

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
              {browserMode ? "Aqlyra Browser Voice" : "Aqlyra Voice"}
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
                    : browserMode
                    ? "Speech recognition may use your browser provider; only approved text is sent to Aqlyra."
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
