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
} from "livekit-client";

import {
  VoiceOrb,
  type VoiceVisualState,
} from "@/components/voice/voice-orb";
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
    const room =
      roomRef.current;

    roomRef.current = null;

    if (room) {
      try {
        await room.localParticipant
          .setMicrophoneEnabled(false);
      } catch {
        // Best-effort cleanup.
      }

      await room.disconnect();
    }

    clearAudioElements();

    setActive(false);
    setStarting(false);
    setMuted(false);
    setAgentState("idle");
    setLiveUserText("");
    setLiveAgentText("");
    setError("");
  }


  async function startCall() {
    if (
      disabled ||
      active ||
      starting
    ) {
      return;
    }

    setStarting(true);
    setError("");
    setLiveUserText("");
    setLiveAgentText("");
    setAgentState("connecting");

    let room: Room | null = null;

    try {
      const response =
        await fetch(
          "/api/voice/session",
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              mode,
              ...(conversationId
                ? {
                    conversation_id:
                      conversationId,
                  }
                : {}),
              title:
                "Voice conversation",
              document_ids:
                documentIds,
            }),
          },
        );

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
            participant ===
            room?.localParticipant
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

      room.on(
        RoomEvent.Disconnected,
        () => {
          roomRef.current = null;

          clearAudioElements();

          setActive(false);
          setStarting(false);
          setMuted(false);
          setAgentState("idle");
        },
      );

      await room.connect(
        session.server_url,
        session.participant_token,
      );

      onConversationStarted?.(
        session.conversation_id,
      );

      await room.localParticipant
        .setMicrophoneEnabled(true);

      setMuted(false);
      setActive(true);
      setStarting(false);

      setAgentState(
        (current) =>
          current === "connecting"
            ? "listening"
            : current,
      );
    } catch (startError) {
      if (room) {
        try {
          await room.disconnect();
        } catch {
          // Best-effort cleanup.
        }
      }

      roomRef.current = null;

      clearAudioElements();

      const message =
        startError instanceof Error
          ? startError.message
          : "Unable to start voice conversation.";

      setError(message);
      setAgentState("error");
      setStarting(false);
      setActive(false);

      onError?.(message);
    }
  }


  async function toggleMute() {
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
          title="Start voice conversation"
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

        <div
          ref={audioContainerRef}
          className="hidden"
        />
      </>
    );
  }


  return (
    <>
      <div className="absolute bottom-[72px] right-4 z-40 w-[280px] overflow-hidden rounded-[24px] border border-[var(--aq-border)] bg-[var(--aq-card)]/95 p-4 shadow-2xl backdrop-blur-xl">
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
              Aqlyra Voice
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
                Speak naturally. Aqlyra is listening.
              </div>
            ) : null}
          </div>

          {error ? (
            <div className="mt-3 w-full rounded-xl border border-red-500/20 bg-red-500/5 px-3 py-2 text-[11px] text-red-500">
              {error}
            </div>
          ) : null}

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
