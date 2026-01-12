"use client";

interface LoadingProps {
  text?: string;
  size?: "sm" | "md" | "lg";
}

export function Loading({ text = "Loading", size = "md" }: LoadingProps) {
  const sizeStyles = {
    sm: "text-xs",
    md: "text-sm",
    lg: "text-base",
  };

  return (
    <div className={`font-mono text-terminal-green ${sizeStyles[size]}`}>
      <span className="inline-flex items-center gap-2">
        <span className="animate-pulse">[</span>
        <span className="animate-pulse" style={{ animationDelay: "0.1s" }}>
          =
        </span>
        <span className="animate-pulse" style={{ animationDelay: "0.2s" }}>
          =
        </span>
        <span className="animate-pulse" style={{ animationDelay: "0.3s" }}>
          =
        </span>
        <span className="animate-pulse" style={{ animationDelay: "0.4s" }}>
          &gt;
        </span>
        <span className="animate-pulse">]</span>
        <span>{text}</span>
      </span>
    </div>
  );
}

export function LoadingSpinner() {
  return (
    <div className="font-mono text-terminal-green animate-spin inline-block">
      |
    </div>
  );
}

export function LoadingDots() {
  return (
    <span className="font-mono text-terminal-green">
      <span className="animate-pulse">.</span>
      <span className="animate-pulse" style={{ animationDelay: "0.2s" }}>
        .
      </span>
      <span className="animate-pulse" style={{ animationDelay: "0.4s" }}>
        .
      </span>
    </span>
  );
}
