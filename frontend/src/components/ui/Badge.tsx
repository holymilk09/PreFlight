"use client";

import { ReactNode } from "react";

interface BadgeProps {
  children: ReactNode;
  variant?: "default" | "success" | "warning" | "error" | "info";
}

const variantStyles = {
  default: "text-terminal-white-dim border-terminal-gray",
  success: "text-terminal-green border-terminal-green",
  warning: "text-terminal-amber border-terminal-amber",
  error: "text-terminal-red border-terminal-red",
  info: "text-terminal-cyan border-terminal-cyan",
};

export function Badge({ children, variant = "default" }: BadgeProps) {
  return (
    <span
      className={`font-mono text-xs px-2 py-0.5 border ${variantStyles[variant]}`}
    >
      {children}
    </span>
  );
}

// Predefined badges for common statuses
export function StatusBadge({
  status,
}: {
  status: "MATCH" | "REVIEW" | "NEW" | "REJECT" | "ACTIVE" | "DEPRECATED";
}) {
  const config: Record<string, { variant: BadgeProps["variant"]; label: string }> = {
    MATCH: { variant: "success", label: "MATCH" },
    REVIEW: { variant: "warning", label: "REVIEW" },
    NEW: { variant: "info", label: "NEW" },
    REJECT: { variant: "error", label: "REJECT" },
    ACTIVE: { variant: "success", label: "ACTIVE" },
    DEPRECATED: { variant: "default", label: "DEPRECATED" },
  };

  const { variant, label } = config[status] || config.MATCH;
  return <Badge variant={variant}>{label}</Badge>;
}
