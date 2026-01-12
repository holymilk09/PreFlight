"use client";

import { ReactNode } from "react";

interface PulseGlowProps {
  children: ReactNode;
  color?: "green" | "amber" | "red" | "cyan";
  intensity?: "low" | "medium" | "high";
  active?: boolean;
  className?: string;
}

const colorStyles = {
  green: {
    low: "shadow-[0_0_5px_#00ff00]",
    medium: "shadow-[0_0_10px_#00ff00,0_0_20px_#00ff0066]",
    high: "shadow-[0_0_15px_#00ff00,0_0_30px_#00ff0088,0_0_45px_#00ff0044]",
  },
  amber: {
    low: "shadow-[0_0_5px_#ffb000]",
    medium: "shadow-[0_0_10px_#ffb000,0_0_20px_#ffb00066]",
    high: "shadow-[0_0_15px_#ffb000,0_0_30px_#ffb00088,0_0_45px_#ffb00044]",
  },
  red: {
    low: "shadow-[0_0_5px_#ff4444]",
    medium: "shadow-[0_0_10px_#ff4444,0_0_20px_#ff444466]",
    high: "shadow-[0_0_15px_#ff4444,0_0_30px_#ff444488,0_0_45px_#ff444444]",
  },
  cyan: {
    low: "shadow-[0_0_5px_#00ffff]",
    medium: "shadow-[0_0_10px_#00ffff,0_0_20px_#00ffff66]",
    high: "shadow-[0_0_15px_#00ffff,0_0_30px_#00ffff88,0_0_45px_#00ffff44]",
  },
};

export function PulseGlow({
  children,
  color = "green",
  intensity = "medium",
  active = true,
  className = "",
}: PulseGlowProps) {
  const glowClass = colorStyles[color][intensity];

  return (
    <div
      className={`
        inline-block
        ${active ? glowClass : ""}
        ${active ? "animate-pulse" : ""}
        transition-shadow duration-300
        ${className}
      `}
    >
      {children}
    </div>
  );
}
