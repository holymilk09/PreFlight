"use client";

import { useEffect, useState, useCallback } from "react";

interface ASCIIDocumentVizProps {
  className?: string;
  state?: "idle" | "scanning" | "extracting" | "matching" | "complete";
  progress?: number;
  onComplete?: () => void;
  autoPlay?: boolean;
  cycleDuration?: number;
}

const documentFrames = {
  idle: [
    "┌────────────────────────┐",
    "│ ░░░░░░░░░░░░░░░░░░░░░░ │",
    "│ ░░░░░░░░░░░░░░░░░░░░░░ │",
    "│ ░░░░░░░░░░░░░░░░░░░░░░ │",
    "│ ░░░░░░░░░░░░░░░░░░░░░░ │",
    "│ ░░░░░░░░░░░░░░░░░░░░░░ │",
    "│ ░░░░░░░░░░░░░░░░░░░░░░ │",
    "└────────────────────────┘",
  ],
  scanning: [
    "┌────────────────────────┐",
    "│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │",
    "│ ░░░░░░░░░░░░░░░░░░░░░░ │",
    "│ ░░░░░░░░░░░░░░░░░░░░░░ │",
    "│ ░░░░░░░░░░░░░░░░░░░░░░ │",
    "│ ░░░░░░░░░░░░░░░░░░░░░░ │",
    "│ ░░░░░░░░░░░░░░░░░░░░░░ │",
    "└────────────────────────┘",
  ],
  extracting: [
    "┌────────────────────────┐",
    "│ ████████████████████░░ │",
    "│ ██████████████░░░░░░░░ │",
    "│ ███████████████████░░░ │",
    "│ ████████░░░░░░░░░░░░░░ │",
    "│ ██████████████████████ │",
    "│ ░░░░░░░░░░░░░░░░░░░░░░ │",
    "└────────────────────────┘",
  ],
  matching: [
    "┌────────────────────────┐",
    "│ ████████████████████░░ │",
    "│ ██████████████░░░░░░░░ │",
    "│ ███████████████████░░░ │",
    "│ ████████░░░░░░░░░░░░░░ │",
    "│ ██████████████████████ │",
    "│ ██████████████████░░░░ │",
    "└────────────────────────┘",
  ],
  complete: [
    "┌────────────────────────┐",
    "│ ██████████████████████ │",
    "│ ██████████████████████ │",
    "│ ██████████████████████ │",
    "│ ██████████████████████ │",
    "│ ██████████████████████ │",
    "│ ██████████████████████ │",
    "└────────────────────────┘",
  ],
};

const stateLabels = {
  idle: "READY",
  scanning: "SCANNING",
  extracting: "EXTRACTING",
  matching: "MATCHING",
  complete: "COMPLETE",
};

const stateColors = {
  idle: "text-terminal-white-dim",
  scanning: "text-terminal-cyan",
  extracting: "text-terminal-amber",
  matching: "text-terminal-green",
  complete: "text-terminal-green",
};

export function ASCIIDocumentViz({
  className = "",
  state = "idle",
  progress = 0,
  onComplete,
  autoPlay = false,
  cycleDuration = 5000,
}: ASCIIDocumentVizProps) {
  const [currentState, setCurrentState] = useState<keyof typeof documentFrames>(state);
  const [currentProgress, setCurrentProgress] = useState(progress);
  const [scanLinePos, setScanLinePos] = useState(0);

  // Auto-cycle through states
  useEffect(() => {
    if (!autoPlay) {
      setCurrentState(state);
      setCurrentProgress(progress);
      return;
    }

    const states: Array<keyof typeof documentFrames> = [
      "idle",
      "scanning",
      "extracting",
      "matching",
      "complete",
    ];
    let stateIndex = 0;
    let progressVal = 0;

    const interval = setInterval(() => {
      progressVal += 5;

      if (progressVal >= 100) {
        progressVal = 0;
        stateIndex = (stateIndex + 1) % states.length;
        setCurrentState(states[stateIndex]);

        if (states[stateIndex] === "complete") {
          onComplete?.();
        }
      }

      setCurrentProgress(progressVal);
    }, cycleDuration / 20);

    return () => clearInterval(interval);
  }, [autoPlay, cycleDuration, state, progress, onComplete]);

  // Animate scan line
  useEffect(() => {
    if (currentState !== "scanning") {
      setScanLinePos(0);
      return;
    }

    const interval = setInterval(() => {
      setScanLinePos((prev) => (prev + 1) % 6);
    }, 150);

    return () => clearInterval(interval);
  }, [currentState]);

  const renderFrame = useCallback(() => {
    const baseFrame = [...documentFrames[currentState]];

    // Add scan line animation for scanning state
    if (currentState === "scanning" && scanLinePos > 0) {
      const lineIndex = scanLinePos;
      if (lineIndex > 0 && lineIndex < 7) {
        baseFrame[lineIndex] = "│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │";
        // Dim previous lines
        for (let i = 1; i < lineIndex; i++) {
          baseFrame[i] = "│ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒ │";
        }
      }
    }

    return baseFrame;
  }, [currentState, scanLinePos]);

  const progressBarWidth = 20;
  const filledWidth = Math.floor((currentProgress / 100) * progressBarWidth);
  const emptyWidth = progressBarWidth - filledWidth;
  const progressBar = `[${"█".repeat(filledWidth)}${"░".repeat(emptyWidth)}]`;

  return (
    <div className={`font-mono ${className}`}>
      {/* Document visualization */}
      <pre
        className={`${stateColors[currentState]} text-sm leading-tight ${
          currentState === "complete" ? "animate-pulse-glow glow-green" : ""
        }`}
      >
        {renderFrame().join("\n")}
      </pre>

      {/* Status and progress */}
      <div className="mt-2 text-center">
        <span
          className={`text-xs ${stateColors[currentState]} ${
            currentState === "scanning" || currentState === "extracting"
              ? "animate-pulse"
              : ""
          }`}
        >
          {stateLabels[currentState]}
        </span>
      </div>

      {/* Progress bar */}
      <div className="mt-1 text-center">
        <span className={`text-xs ${stateColors[currentState]}`}>
          {progressBar} {currentProgress}%
        </span>
      </div>
    </div>
  );
}

// Smaller inline version for tables/lists
export function ASCIIDocumentMini({
  state = "idle",
  className = "",
}: {
  state?: "idle" | "scanning" | "extracting" | "matching" | "complete";
  className?: string;
}) {
  const miniFrames = {
    idle: "░░░░",
    scanning: "▒▓▒░",
    extracting: "██▓░",
    matching: "███▓",
    complete: "████",
  };

  return (
    <span className={`font-mono text-terminal-green ${className}`}>
      [{miniFrames[state]}]
    </span>
  );
}
