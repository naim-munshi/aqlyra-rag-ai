type AqlyraLogoProps = {
  size?: number;
  showName?: boolean;
};

export function AqlyraLogo({
  size = 44,
  showName = true,
}: AqlyraLogoProps) {
  return (
    <div className="flex items-center gap-3">
      <svg
        width={size}
        height={size}
        viewBox="0 0 120 120"
        fill="none"
        aria-label="Aqlyra"
      >
        <defs>
          <linearGradient
            id="aqlyra-gradient"
            x1="20"
            y1="15"
            x2="95"
            y2="100"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="#126BFA" />
            <stop offset="1" stopColor="#1AC7FA" />
          </linearGradient>
        </defs>

        <path
          d="M60 15L91 33V70L60 89L29 70V33L60 15Z"
          fill="#071426"
          stroke="#126BFA"
          strokeWidth="4"
        />

        <path
          d="M60 27L82 40L60 53L38 40L60 27Z"
          fill="url(#aqlyra-gradient)"
        />

        <path
          d="M39 51L60 64L81 51V63L60 76L39 63V51Z"
          fill="#0B2A54"
          stroke="#126BFA"
          strokeWidth="2"
        />

        <path
          d="M47 70L60 78L73 70V80L60 88L47 80V70Z"
          fill="#081F3D"
        />

        <path
          d="M27 35C15 49 16 72 31 86"
          stroke="#126BFA"
          strokeWidth="3"
          strokeLinecap="round"
        />

        <path
          d="M93 35C105 49 104 72 89 86"
          stroke="#126BFA"
          strokeWidth="3"
          strokeLinecap="round"
        />

        <circle cx="23" cy="32" r="5" fill="#1AC7FA" />
        <circle cx="97" cy="88" r="5" fill="#1AC7FA" />
      </svg>

      {showName && (
        <div className="leading-none">
          <div className="text-[20px] font-bold tracking-tight">
            Aqlyra
          </div>

          <div className="mt-1 text-[9px] font-semibold tracking-[0.2em] text-[#1ac7fa]">
            RAG AI
          </div>
        </div>
      )}
    </div>
  );
}