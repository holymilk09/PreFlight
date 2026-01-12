"use client";

import { useEffect, useState, useCallback } from "react";

interface TypewriterTextProps {
  text: string;
  speed?: number;
  delay?: number;
  cursor?: boolean;
  cursorChar?: string;
  className?: string;
  onComplete?: () => void;
  loop?: boolean;
  pauseDuration?: number;
}

export function TypewriterText({
  text,
  speed = 50,
  delay = 0,
  cursor = true,
  cursorChar = "█",
  className = "",
  onComplete,
  loop = false,
  pauseDuration = 2000,
}: TypewriterTextProps) {
  const [displayText, setDisplayText] = useState("");
  const [showCursor, setShowCursor] = useState(true);

  const typeText = useCallback(() => {
    // Check for reduced motion preference
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    if (prefersReducedMotion) {
      setDisplayText(text);
      onComplete?.();
      return;
    }

    let currentIndex = 0;

    const typeChar = () => {
      if (currentIndex < text.length) {
        setDisplayText(text.slice(0, currentIndex + 1));
        currentIndex++;
        setTimeout(typeChar, speed);
      } else {
        onComplete?.();

        if (loop) {
          setTimeout(() => {
            eraseText();
          }, pauseDuration);
        }
      }
    };

    const eraseText = () => {
      let eraseIndex = text.length;

      const eraseChar = () => {
        if (eraseIndex > 0) {
          eraseIndex--;
          setDisplayText(text.slice(0, eraseIndex));
          setTimeout(eraseChar, speed / 2);
        } else {
          setTimeout(() => {
            typeText();
          }, pauseDuration / 2);
        }
      };

      eraseChar();
    };

    typeChar();
  }, [text, speed, onComplete, loop, pauseDuration]);

  useEffect(() => {
    const timeoutId = setTimeout(typeText, delay);
    return () => clearTimeout(timeoutId);
  }, [typeText, delay]);

  // Cursor blink effect
  useEffect(() => {
    if (!cursor) return;

    const blinkInterval = setInterval(() => {
      setShowCursor((prev) => !prev);
    }, 530);

    return () => clearInterval(blinkInterval);
  }, [cursor]);

  return (
    <span className={className}>
      {displayText}
      {cursor && (
        <span
          className={`${showCursor ? "opacity-100" : "opacity-0"} transition-opacity duration-100`}
        >
          {cursorChar}
        </span>
      )}
    </span>
  );
}
