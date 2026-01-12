"use client";

import { useEffect, useState } from "react";

interface SparklineProps {
  data: number[];
  variant?: "default" | "success" | "warning" | "error";
  height?: number;
  animated?: boolean;
  delay?: number;
}

const chars = "▁▂▃▄▅▆▇█";

const variantColors = {
  default: "text-terminal-green",
  success: "text-terminal-green",
  warning: "text-terminal-amber",
  error: "text-terminal-red",
};

export function Sparkline({
  data,
  variant = "default",
  height = 8,
  animated = false,
  delay = 0,
}: SparklineProps) {
  const [visibleBars, setVisibleBars] = useState(animated ? 0 : data.length);

  useEffect(() => {
    if (!animated || !data.length) {
      setVisibleBars(data.length);
      return;
    }

    // Check for reduced motion
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    if (prefersReducedMotion) {
      setVisibleBars(data.length);
      return;
    }

    setVisibleBars(0);

    const startTimeout = setTimeout(() => {
      let currentBar = 0;
      const interval = setInterval(() => {
        currentBar++;
        setVisibleBars(currentBar);

        if (currentBar >= data.length) {
          clearInterval(interval);
        }
      }, 50);

      return () => clearInterval(interval);
    }, delay);

    return () => clearTimeout(startTimeout);
  }, [data.length, animated, delay]);

  if (!data.length) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const sparkline = data
    .slice(0, visibleBars)
    .map((v) => {
      const normalized = (v - min) / range;
      const index = Math.min(
        height - 1,
        Math.floor(normalized * (height - 1))
      );
      return chars[index];
    })
    .join("");

  // Pad with empty space for remaining bars during animation
  const padding = animated ? " ".repeat(data.length - visibleBars) : "";

  return (
    <span className={`font-mono ${variantColors[variant]}`}>
      {sparkline}
      {padding}
    </span>
  );
}
