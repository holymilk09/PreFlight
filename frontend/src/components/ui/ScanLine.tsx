"use client";

interface ScanLineProps {
  active?: boolean;
  color?: "green" | "amber" | "red" | "cyan" | "white";
  speed?: "slow" | "normal" | "fast";
  direction?: "down" | "up";
  className?: string;
}

const colorClasses = {
  green: "bg-gradient-to-b from-transparent via-terminal-green/30 to-transparent",
  amber: "bg-gradient-to-b from-transparent via-terminal-amber/30 to-transparent",
  red: "bg-gradient-to-b from-transparent via-terminal-red/30 to-transparent",
  cyan: "bg-gradient-to-b from-transparent via-terminal-cyan/30 to-transparent",
  white: "bg-gradient-to-b from-transparent via-white/20 to-transparent",
};

const speedClasses = {
  slow: "[animation-duration:3s]",
  normal: "[animation-duration:2s]",
  fast: "[animation-duration:1s]",
};

export function ScanLine({
  active = true,
  color = "green",
  speed = "normal",
  direction = "down",
  className = "",
}: ScanLineProps) {
  if (!active) return null;

  const animationClass = direction === "down" ? "animate-scan-down" : "animate-scan-up";

  return (
    <div
      className={`
        absolute inset-0 pointer-events-none overflow-hidden
        ${className}
      `}
    >
      <div
        className={`
          absolute left-0 right-0 h-8
          ${colorClasses[color]}
          ${animationClass}
          ${speedClasses[speed]}
        `}
      />
    </div>
  );
}

// CRT-style scanlines overlay
interface CRTOverlayProps {
  intensity?: "light" | "medium" | "heavy";
  className?: string;
}

export function CRTOverlay({
  intensity = "light",
  className = "",
}: CRTOverlayProps) {
  const opacityMap = {
    light: "rgba(0, 0, 0, 0.05)",
    medium: "rgba(0, 0, 0, 0.1)",
    heavy: "rgba(0, 0, 0, 0.15)",
  };

  const opacity = opacityMap[intensity];

  return (
    <div
      className={`absolute inset-0 pointer-events-none z-10 ${className}`}
      style={{
        background: `repeating-linear-gradient(
          0deg,
          transparent,
          transparent 2px,
          ${opacity} 2px,
          ${opacity} 4px
        )`,
      }}
    />
  );
}
