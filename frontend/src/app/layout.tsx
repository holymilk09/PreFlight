import type { Metadata } from "next";
import { JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/AuthContext";

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "PreFlight - Document Extraction Control Plane",
  description:
    "Know when your OCR is drifting. Govern document extraction pipelines without touching documents.",
  keywords: [
    "OCR",
    "document extraction",
    "drift detection",
    "ML monitoring",
    "document processing",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${jetbrainsMono.variable} font-mono bg-terminal-black text-terminal-green min-h-screen antialiased`}
      >
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
