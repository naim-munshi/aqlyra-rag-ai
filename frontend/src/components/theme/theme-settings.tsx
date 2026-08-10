"use client";

import { useSyncExternalStore } from "react";
import { Monitor, Moon, Sun, X } from "lucide-react";
import { useTheme } from "next-themes";

type ThemeSettingsProps = {
  open: boolean;
  onClose: () => void;
};

const themeOptions = [
  {
    value: "system",
    label: "System",
    description: "Match your device appearance",
    icon: Monitor,
  },
  {
    value: "light",
    label: "Light",
    description: "Bright workspace appearance",
    icon: Sun,
  },
  {
    value: "dark",
    label: "Dark",
    description: "Aqlyra dark workspace",
    icon: Moon,
  },
] as const;

function useMounted() {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}

export function ThemeSettings({
  open,
  onClose,
}: ThemeSettingsProps) {
  const { theme, setTheme } = useTheme();
  const mounted = useMounted();

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--aq-overlay)] p-4 backdrop-blur-sm"
      onMouseDown={onClose}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-label="Aqlyra settings"
        onMouseDown={(event) => event.stopPropagation()}
        className="w-full max-w-[540px] rounded-2xl border border-[var(--aq-border)] bg-[var(--aq-panel)] shadow-2xl"
      >
        <header className="flex items-center justify-between border-b border-[var(--aq-border)] px-6 py-5">
          <div>
            <h2 className="text-lg font-bold text-[var(--aq-text)]">
              Settings
            </h2>

            <p className="mt-1 text-xs text-[var(--aq-muted)]">
              Personalize your Aqlyra workspace.
            </p>
          </div>

          <button
            type="button"
            aria-label="Close settings"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--aq-border)] text-[var(--aq-muted)] transition hover:bg-[var(--aq-control)] hover:text-[var(--aq-text)]"
          >
            <X size={17} />
          </button>
        </header>

        <div className="p-6">
          <div>
            <h3 className="text-sm font-semibold text-[var(--aq-text)]">
              Appearance
            </h3>

            <p className="mt-1 text-xs text-[var(--aq-muted)]">
              Choose how Aqlyra looks on this device.
            </p>
          </div>

          <div className="mt-5 grid grid-cols-3 gap-3">
            {themeOptions.map((option) => {
              const Icon = option.icon;

              const active =
                mounted && theme === option.value;

              return (
                <button
                  type="button"
                  key={option.value}
                  onClick={() => setTheme(option.value)}
                  className={[
                    "relative flex min-h-[132px] flex-col rounded-xl border p-4 text-left transition",
                    active
                      ? "border-[var(--aq-blue)] bg-[var(--aq-blue-soft)]"
                      : "border-[var(--aq-border)] bg-[var(--aq-card)] hover:border-[var(--aq-border-hover)]",
                  ].join(" ")}
                >
                  <span
                    className={[
                      "flex h-9 w-9 items-center justify-center rounded-lg",
                      active
                        ? "bg-[var(--aq-blue)] text-white"
                        : "bg-[var(--aq-control)] text-[var(--aq-muted)]",
                    ].join(" ")}
                  >
                    <Icon size={17} />
                  </span>

                  <span className="mt-4 text-sm font-semibold text-[var(--aq-text)]">
                    {option.label}
                  </span>

                  <span className="mt-1 text-[10px] leading-4 text-[var(--aq-muted)]">
                    {option.description}
                  </span>

                  {active && (
                    <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-[var(--aq-blue)] text-[10px] font-bold text-white">
                      ✓
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          <div className="mt-6 rounded-xl border border-[var(--aq-border)] bg-[var(--aq-card)] p-4">
            <p className="text-xs font-semibold text-[var(--aq-text)]">
              Theme preference
            </p>

            <p className="mt-1 text-[11px] leading-5 text-[var(--aq-muted)]">
              System follows your operating system. Light and Dark keep
              Aqlyra fixed to the selected appearance.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}