"use client";

import { useEffect, useState, useCallback } from "react";

interface GlitchTextProps {
  text: string;
  intensity?: "low" | "medium" | "high";
  continuous?: boolean;
  onHover?: boolean;
  className?: string;
  color?: "green" | "red" | "amber" | "cyan";
}

const glitchChars = "!@#$%^&*()_+-=[]{}|;:,.<>?/~`0123456789";

const intensityConfig = {
  low: { charChangeRate: 0.1, interval: 150, duration: 200 },
  medium: { charChangeRate: 0.2, interval: 100, duration: 300 },
  high: { charChangeRate: 0.4, interval: 50, duration: 500 },
};

const colorClasses = {
  green: "text-terminal-green",
  red: "text-terminal-red",
  amber: "text-terminal-amber",
  cyan: "text-terminal-cyan",
};

export function GlitchText({
  text,
  intensity = "medium",
  continuous = false,
  onHover = false,
  className = "",
  color = "green",
}: GlitchTextProps) {
  const [displayText, setDisplayText] = useState(text);
  const [isGlitching, setIsGlitching] = useState(continuous);
  const config = intensityConfig[intensity];

  const glitch = useCallback(() => {
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    if (prefersReducedMotion) {
      return;
    }

    let iterations = 0;
    const maxIterations = config.duration / config.interval;

    const glitchInterval = setInterval(() => {
      setDisplayText(
        text
          .split("")
          .map((char) => {
            if (char === " ") return char;
            return Math.random() < config.charChangeRate
              ? glitchChars[Math.floor(Math.random() * glitchChars.length)]
              : char;
          })
          .join("")
      );

      iterations++;

      if (iterations >= maxIterations && !continuous) {
        clearInterval(glitchInterval);
        setDisplayText(text);
        setIsGlitching(false);
      }
    }, config.interval);

    return () => clearInterval(glitchInterval);
  }, [text, config, continuous]);

  useEffect(() => {
    if (continuous) {
      setIsGlitching(true);
      const cleanup = glitch();

      // Re-trigger glitch periodically
      const loopInterval = setInterval(() => {
        glitch();
      }, config.duration + 2000);

      return () => {
        cleanup?.();
        clearInterval(loopInterval);
      };
    }
  }, [continuous, glitch, config.duration]);

  useEffect(() => {
    if (isGlitching && !continuous) {
      const cleanup = glitch();
      return cleanup;
    }
  }, [isGlitching, glitch, continuous]);

  const handleMouseEnter = () => {
    if (onHover && !isGlitching) {
      setIsGlitching(true);
    }
  };

  const handleMouseLeave = () => {
    if (onHover) {
      setDisplayText(text);
      setIsGlitching(false);
    }
  };

  return (
    <span
      className={`${colorClasses[color]} ${isGlitching ? "animate-glitch-loop" : ""} ${className}`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      data-text={text}
    >
      {displayText}
    </span>
  );
}
