"use client";

import { ButtonHTMLAttributes, ReactNode } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  fullWidth?: boolean;
}

const variantStyles = {
  primary:
    "bg-terminal-green text-terminal-black hover:bg-terminal-green-dim",
  secondary:
    "bg-transparent text-terminal-green border border-terminal-green hover:bg-terminal-green hover:text-terminal-black",
  ghost:
    "bg-transparent text-terminal-green hover:bg-terminal-darkgray",
  danger:
    "bg-terminal-red text-terminal-black hover:bg-terminal-red-dim",
};

const sizeStyles = {
  sm: "px-2 py-1 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-6 py-3 text-base",
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  fullWidth = false,
  disabled,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      className={`
        font-mono transition-colors duration-150
        disabled:opacity-50 disabled:cursor-not-allowed
        ${variantStyles[variant]}
        ${sizeStyles[size]}
        ${fullWidth ? "w-full" : ""}
        ${className}
      `}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <span className="inline-flex items-center gap-2">
          <span className="animate-pulse">[...]</span>
          {children}
        </span>
      ) : (
        children
      )}
    </button>
  );
}
