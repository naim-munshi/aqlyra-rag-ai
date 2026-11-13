export type VoiceVisualState =
  | "idle"
  | "connecting"
  | "listening"
  | "thinking"
  | "speaking"
  | "error";

type VoiceOrbProps = {
  state: VoiceVisualState;
  muted?: boolean;
  compact?: boolean;
};

export function VoiceOrb({
  state,
  muted = false,
  compact = false,
}: VoiceOrbProps) {
  const active =
    state === "listening" ||
    state === "speaking";

  const thinking =
    state === "thinking" ||
    state === "connecting";

  return (
    <div
      aria-hidden="true"
      className={[
        "relative flex shrink-0 items-center justify-center",
        compact ? "h-12 w-12" : "h-24 w-24",
      ].join(" ")}
    >
      <div
        className={[
          "absolute rounded-full border border-[var(--aq-cyan)]/30",
          compact ? "inset-1" : "inset-0",
          active && !muted
            ? "animate-ping"
            : "",
        ].join(" ")}
      />

      <div
        className={[
          "absolute inset-2 rounded-full border border-[var(--aq-blue)]/50",
          thinking
            ? "animate-spin border-t-transparent"
            : "",
        ].join(" ")}
      />

      <div
        className={[
          "absolute rounded-full border border-[var(--aq-cyan)]/40",
          compact ? "inset-3" : "inset-4",
          state === "speaking" && !muted
            ? "animate-pulse"
            : "",
        ].join(" ")}
      />

      <div
        className={[
          "relative flex items-center justify-center rounded-full",
          compact ? "h-7 w-7" : "h-12 w-12",
          "border border-[var(--aq-border)] bg-[var(--aq-control)]",
          "shadow-[0_0_30px_rgba(34,211,238,0.18)]",
          muted
            ? "opacity-40"
            : "",
        ].join(" ")}
      >
        <div
          className={[
            compact ? "h-3 w-3 rounded-full" : "h-5 w-5 rounded-full",
            state === "error"
              ? "bg-red-500"
              : "bg-[var(--aq-cyan)]",
            state === "speaking"
              ? "animate-pulse"
              : "",
          ].join(" ")}
        />
      </div>

      <div className="absolute inset-x-2 top-1/2 flex -translate-y-1/2 items-center justify-center gap-1">
        {[5, 10, 16, 10, 5].map(
          (height, index) => (
            <span
              key={index}
              style={{
                height:
                  state === "speaking"
                    ? `${compact ? Math.round(height * 0.7) : height}px`
                    : "3px",
              }}
              className={[
                "w-[2px] rounded-full bg-white/70 transition-all duration-150",
                state === "speaking"
                  ? "animate-pulse"
                  : "",
              ].join(" ")}
            />
          ),
        )}
      </div>
    </div>
  );
}
