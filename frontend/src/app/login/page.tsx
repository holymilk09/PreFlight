"use client";

import Link from "next/link";
import { useState } from "react";
import { Box, Button, Input } from "@/components/ui";
import { useAuth } from "@/lib/AuthContext";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const result = await login(email, password);
      if (!result.success) {
        setError(result.error || "Login failed");
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

        <Box title="LOGIN" variant="highlight">
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
              placeholder="********"
              required
            />

            <div className="flex items-center justify-between text-sm">
              <label className="flex items-center gap-2 text-terminal-white-dim">
                <input
                  type="checkbox"
                  className="bg-terminal-darkgray border border-terminal-gray"
                />
                Remember me
              </label>
              <Link
                href="/forgot-password"
                className="text-terminal-green hover:underline"
              >
                Forgot password?
              </Link>
            </div>

            <Button type="submit" variant="primary" disabled={loading} fullWidth>
              {loading ? "[AUTHENTICATING...]" : "[LOGIN]"}
            </Button>

            <p className="text-center text-terminal-white-dim text-sm">
              Don&apos;t have an account?{" "}
              <Link href="/signup" className="text-terminal-green hover:underline">
                Sign up
              </Link>
            </p>
          </form>
        </Box>

        <div className="mt-8 text-center">
          <pre className="text-terminal-gray text-xs">
            {`┌─────────────────────────────────────┐
│  Secure authentication enabled      │
│  All connections encrypted (TLS)    │
└─────────────────────────────────────┘`}
          </pre>
        </div>
      </div>
    </div>
  );
}
