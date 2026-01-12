"use client";

import Link from "next/link";
import { useState } from "react";
import { Box, Button, Input } from "@/components/ui";
import { useAuth } from "@/lib/AuthContext";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { signup } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setLoading(true);

    try {
      const result = await signup(email, password);
      if (!result.success) {
        setError(result.error || "Signup failed");
      }
      // Redirect is handled by AuthContext on success
    } catch {
      setError("An unexpected error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-[#0a0a0a]">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link href="/" className="text-terminal-green font-bold text-2xl">
            [PREFLIGHT]
          </Link>
          <p className="text-terminal-white-dim mt-2">
            Document Extraction Control Plane
          </p>
        </div>

        <Box title="CREATE ACCOUNT" variant="highlight">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="text-terminal-red text-sm border border-terminal-red px-3 py-2">
                [ERROR] {error}
              </div>
            )}

            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              required
            />

            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Min. 8 characters"
              hint="Use a strong, unique password"
              required
            />

            <Input
              label="Confirm Password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Re-enter password"
              required
            />

            <div className="text-sm text-terminal-white-dim">
              <label className="flex items-start gap-2">
                <input
                  type="checkbox"
                  required
                  className="mt-1 bg-terminal-darkgray border border-terminal-gray"
                />
                <span>
                  I agree to the{" "}
                  <Link
                    href="/terms"
                    className="text-terminal-green hover:underline"
                  >
                    Terms of Service
                  </Link>{" "}
                  and{" "}
                  <Link
                    href="/privacy"
                    className="text-terminal-green hover:underline"
                  >
                    Privacy Policy
                  </Link>
                </span>
              </label>
            </div>

            <Button type="submit" variant="primary" disabled={loading} fullWidth>
              {loading ? "[CREATING ACCOUNT...]" : "[CREATE ACCOUNT]"}
            </Button>

            <p className="text-center text-terminal-white-dim text-sm">
              Already have an account?{" "}
              <Link href="/login" className="text-terminal-green hover:underline">
                Log in
              </Link>
            </p>
          </form>
        </Box>

        <div className="mt-8 text-center">
          <pre className="text-terminal-gray text-xs">
            {`┌─────────────────────────────────────┐
│  No credit card required            │
│  1,000 free evaluations/month       │
│  Full API access included           │
└─────────────────────────────────────┘`}
          </pre>
        </div>
      </div>
    </div>
  );
}
