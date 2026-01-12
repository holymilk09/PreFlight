"use client";

import { useEffect, useState } from "react";

interface ProgressProps {
  value: number;
  max?: number;
  width?: number;
  showPercent?: boolean;
  variant?: "default" | "success" | "warning" | "error";
  animated?: boolean;
  delay?: number;
  duration?: number;
}

const variantColors = {
  default: "text-terminal-green",
  success: "text-terminal-green",
  warning: "text-terminal-amber",
  error: "text-terminal-red",
};

export function Progress({
  value,
  max = 100,
  width = 20,
  showPercent = true,
  variant = "default",
  animated = false,
  delay = 0,
  duration = 800,
}: ProgressProps) {
  const [displayValue, setDisplayValue] = useState(animated ? 0 : value);

  useEffect(() => {
    if (!animated) {
      setDisplayValue(value);
      return;
    }

    // Check for reduced motion
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    if (prefersReducedMotion) {
      setDisplayValue(value);
      return;
    }

    const startTime = Date.now() + delay;
    let animationId: number;

    const animate = () => {
      const now = Date.now();
      const elapsed = now - startTime;

      if (elapsed < 0) {
        animationId = requestAnimationFrame(animate);
        return;
      }

      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayValue(eased * value);

      if (progress < 1) {
        animationId = requestAnimationFrame(animate);
      } else {
        setDisplayValue(value);
      }
    };

    animationId = requestAnimationFrame(animate);

    return () => cancelAnimationFrame(animationId);
  }, [value, animated, delay, duration]);

  const percent = Math.min(100, Math.max(0, (displayValue / max) * 100));
  const filled = Math.round((percent / 100) * width);
  const empty = width - filled;

  return (
    <span className={`font-mono ${variantColors[variant]}`}>
      [{"█".repeat(filled)}
      {"░".repeat(empty)}]{showPercent && ` ${Math.round(percent)}%`}
    </span>
  );
}
