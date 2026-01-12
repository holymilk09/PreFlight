"use client";

import { ReactNode } from "react";

interface BoxProps {
  title?: string;
  children: ReactNode;
  variant?: "default" | "highlight" | "error" | "warning";
  className?: string;
}

const variantStyles = {
  default: "border-terminal-gray",
  highlight: "border-terminal-green",
  error: "border-terminal-red",
  warning: "border-terminal-amber",
};

const titleStyles = {
  default: "text-terminal-white-dim",
  highlight: "text-terminal-green",
  error: "text-terminal-red",
  warning: "text-terminal-amber",
};

export function Box({
  title,
  children,
  variant = "default",
  className = "",
}: BoxProps) {
  const borderColor = variantStyles[variant];
  const titleColor = titleStyles[variant];

  return (
    <div className={`font-mono ${className}`}>
      {/* Top border with optional title */}
      <div className={`${borderColor} border-t border-l border-r flex`}>
        <span className={borderColor}>┌</span>
        {title ? (
          <>
            <span className={borderColor}>─ </span>
            <span className={titleColor}>{title}</span>
            <span className={borderColor}> </span>
            <span className={`${borderColor} flex-1 overflow-hidden`}>
              {"─".repeat(100)}
            </span>
          </>
        ) : (
          <span className={`${borderColor} flex-1 overflow-hidden`}>
            {"─".repeat(100)}
          </span>
        )}
        <span className={borderColor}>┐</span>
      </div>

      {/* Content with side borders */}
      <div className={`${borderColor} border-l border-r px-3 py-2`}>
        {children}
      </div>

      {/* Bottom border */}
      <div className={`${borderColor} border-b border-l border-r flex`}>
        <span className={borderColor}>└</span>
        <span className={`${borderColor} flex-1 overflow-hidden`}>
          {"─".repeat(100)}
        </span>
        <span className={borderColor}>┘</span>
      </div>
    </div>
  );
}
