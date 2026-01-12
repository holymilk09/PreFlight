"use client";

import { InputHTMLAttributes, forwardRef } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, className = "", ...props }, ref) => {
    return (
      <div className="font-mono">
        {label && (
          <label className="block text-terminal-white-dim text-sm mb-1">
            {label}
          </label>
        )}
        <input
          ref={ref}
          className={`
            w-full bg-terminal-darkgray text-terminal-green
            border px-3 py-2
            focus:outline-none focus:border-terminal-green
            placeholder:text-terminal-gray
            ${error ? "border-terminal-red" : "border-terminal-gray"}
            ${className}
          `}
          {...props}
        />
        {error && (
          <p className="text-terminal-red text-xs mt-1">{error}</p>
        )}
        {hint && !error && (
          <p className="text-terminal-white-dim text-xs mt-1">{hint}</p>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";
