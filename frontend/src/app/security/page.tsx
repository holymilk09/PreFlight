"use client";

import Link from "next/link";

// Reuse header style from landing page
function Header() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-[#0a0a0a]/95 backdrop-blur-md border-b border-white/5">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <Link href="/" className="text-white font-medium text-xl tracking-tight">
          PreFlight
        </Link>
        <nav className="hidden md:flex items-center gap-8">
          <Link href="/#product" className="text-white/60 hover:text-white transition-colors text-sm">
            Product
          </Link>
          <Link href="/#how-it-works" className="text-white/60 hover:text-white transition-colors text-sm">
            How It Works
          </Link>
          <Link href="/faq" className="text-white/60 hover:text-white transition-colors text-sm">
            FAQ
          </Link>
          <Link href="/security" className="text-white transition-colors text-sm">
            Security
          </Link>
          <Link href="/login" className="text-white/60 hover:text-white transition-colors text-sm">
            Sign In
          </Link>
          <Link
            href="/signup"
            className="bg-white text-black px-4 py-2 rounded-full text-sm font-medium hover:bg-white/90 transition-colors"
          >
            Get Started
          </Link>
        </nav>
      </div>
    </header>
  );
}

// Footer
function Footer() {
  return (
    <footer className="border-t border-white/5 py-12 px-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="text-white font-medium">PreFlight</div>
          <div className="flex gap-8 text-white/40 text-sm">
            <Link href="/docs" className="hover:text-white transition-colors">Documentation</Link>
            <Link href="/faq" className="hover:text-white transition-colors">FAQ</Link>
            <Link href="/security" className="hover:text-white transition-colors">Security</Link>
            <Link href="/terms" className="hover:text-white transition-colors">Terms</Link>
          </div>
          <div className="text-white/30 text-sm">
            &copy; {new Date().getFullYear()} PreFlight
          </div>
        </div>
      </div>
    </footer>
  );
}

export default function SecurityPage() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      <Header />

      <main className="pt-32 pb-20 px-6">
        <div className="max-w-5xl mx-auto">
          {/* Hero */}
          <div className="text-center mb-20">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 mb-8">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="text-emerald-400 text-sm font-medium">Zero Document Access</span>
            </div>
            <h1 className="text-4xl md:text-6xl font-bold text-white mb-6">
              Security by Design
            </h1>
            <p className="text-xl text-white/50 max-w-2xl mx-auto">
              PreFlight is architected so we can never see your documents.
              Not by policy&mdash;by design.
            </p>
          </div>

          {/* The Big Picture - What we see vs don't see */}
          <div className="mb-20">
            <h2 className="text-2xl font-bold text-white mb-8 text-center">
              What We Receive vs What We Never See
            </h2>
            <div className="grid md:grid-cols-2 gap-8">
              {/* What we receive */}
              <div className="bg-emerald-500/5 rounded-2xl border border-emerald-500/20 p-8">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center">
                    <span className="text-emerald-400 text-xl">+</span>
                  </div>
                  <h3 className="text-xl font-bold text-emerald-400">What We Analyze</h3>
                </div>
                <ul className="space-y-4">
                  {[
                    { item: "Element counts", desc: "How many tables, text blocks, images" },
                    { item: "Bounding boxes", desc: "Position coordinates (x, y, width, height)" },
                    { item: "Layout structure", desc: "Columns, headers, footers detected" },
                    { item: "Confidence scores", desc: "Your extractor's certainty metrics" },
                    { item: "Document hash", desc: "SHA-256 you generate (we can't reverse it)" },
                  ].map((row) => (
                    <li key={row.item} className="flex items-start gap-3">
                      <span className="text-emerald-400 mt-1">+</span>
                      <div>
                        <span className="text-white/90 font-medium">{row.item}</span>
                        <span className="text-white/50 text-sm block">{row.desc}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

              {/* What we never see */}
              <div className="bg-red-500/5 rounded-2xl border border-red-500/20 p-8">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center">
                    <span className="text-red-400 text-xl">&times;</span>
                  </div>
                  <h3 className="text-xl font-bold text-red-400">What We Never See</h3>
                </div>
                <ul className="space-y-4">
                  {[
                    { item: "Document images", desc: "PDFs, scans, photos - never sent" },
                    { item: "Extracted text", desc: "Words, sentences, paragraphs - never sent" },
                    { item: "Field values", desc: "Names, amounts, dates - never sent" },
                    { item: "PII / PHI", desc: "Personal or health info - never sent" },
                    { item: "File contents", desc: "Raw bytes - never sent" },
                  ].map((row) => (
                    <li key={row.item} className="flex items-start gap-3">
                      <span className="text-red-400 mt-1">&times;</span>
                      <div>
                        <span className="text-white/90 font-medium">{row.item}</span>
                        <span className="text-white/50 text-sm block">{row.desc}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          {/* API Schema Proof */}
          <div className="mb-20">
            <h2 className="text-2xl font-bold text-white mb-4 text-center">
              Technical Proof: Our API Schema
            </h2>
            <p className="text-white/50 text-center mb-8 max-w-2xl mx-auto">
              This is exactly what our API accepts. No fields for document content exist.
            </p>
            <div className="bg-[#0d0d0d] rounded-2xl border border-white/10 p-6 md:p-8 font-mono text-sm overflow-x-auto">
              <div className="text-white/40 mb-4">POST /v1/evaluate</div>
              <pre className="text-emerald-400">{`{
  "layout_fingerprint": "a1b2c3d4...",
  "structural_features": {
    "element_count": 45,
    "table_count": 2,
    "text_block_count": 30,
    "bounding_boxes": [
      { "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.1 }
    ]
  },
  "extractor_metadata": {
    "vendor": "aws_textract",
    "confidence": 0.95
  },
  "client_doc_hash": "xyz789..."
}`}</pre>
              <div className="mt-6 pt-6 border-t border-white/10 space-y-2">
                <div className="text-white/50 text-sm">
                  All fields are <span className="text-emerald-400">counts</span>, <span className="text-emerald-400">coordinates</span>, or <span className="text-emerald-400">hashes</span>.
                </div>
                <div className="text-white/40 text-sm">
                  <span className="text-red-400 font-bold">Fields that DO NOT exist: </span>
                  document_image, extracted_text, field_values, pdf_content
                </div>
              </div>
            </div>
          </div>

          {/* Trust Architecture */}
          <div className="mb-20">
            <h2 className="text-2xl font-bold text-white mb-8 text-center">
              Trust Architecture
            </h2>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[
                {
                  icon: "🔐",
                  title: "API Contract",
                  desc: "No content fields exist in our schema. Architecturally impossible to send document content."
                },
                {
                  icon: "🔒",
                  title: "TLS 1.3 Encryption",
                  desc: "All data in transit is encrypted with modern TLS. Certificate pinning available for enterprise."
                },
                {
                  icon: "🗄️",
                  title: "Metadata-Only Storage",
                  desc: "We only store structural metadata and your hashes. No content ever touches our systems."
                },
                {
                  icon: "👥",
                  title: "Multi-Tenant Isolation",
                  desc: "PostgreSQL Row-Level Security ensures complete tenant isolation at the database level."
                },
                {
                  icon: "📋",
                  title: "Audit Logging",
                  desc: "Every API call is logged with timestamps, request IDs, and actor identification."
                },
                {
                  icon: "🛡️",
                  title: "SOC 2 Type II",
                  desc: "Third-party audited security controls. Annual penetration testing and vulnerability assessments."
                },
              ].map((item) => (
                <div key={item.title} className="bg-white/[0.02] rounded-xl border border-white/10 p-6">
                  <div className="text-3xl mb-4">{item.icon}</div>
                  <h3 className="text-lg font-bold text-white mb-2">{item.title}</h3>
                  <p className="text-white/50 text-sm">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Data Flow Diagram */}
          <div className="mb-20">
            <h2 className="text-2xl font-bold text-white mb-8 text-center">
              How Data Flows
            </h2>
            <div className="bg-white/[0.02] rounded-2xl border border-white/10 p-8">
              <div className="flex flex-col md:flex-row items-center justify-between gap-8">
                {/* Your System */}
                <div className="text-center">
                  <div className="w-20 h-20 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mx-auto mb-4">
                    <span className="text-3xl">🏢</span>
                  </div>
                  <div className="text-white font-medium">Your System</div>
                  <div className="text-white/40 text-sm">Documents stay here</div>
                </div>

                {/* Arrow 1 */}
                <div className="flex flex-col items-center">
                  <div className="text-white/20 text-2xl">→</div>
                  <div className="text-xs text-emerald-400 font-medium">Metadata only</div>
                </div>

                {/* PreFlight */}
                <div className="text-center">
                  <div className="w-20 h-20 rounded-2xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center mx-auto mb-4">
                    <span className="text-2xl font-bold text-emerald-400">PF</span>
                  </div>
                  <div className="text-emerald-400 font-medium">PreFlight</div>
                  <div className="text-white/40 text-sm">Analyzes structure</div>
                </div>

                {/* Arrow 2 */}
                <div className="flex flex-col items-center">
                  <div className="text-white/20 text-2xl">→</div>
                  <div className="text-xs text-emerald-400 font-medium">Decision + rules</div>
                </div>

                {/* Your System again */}
                <div className="text-center">
                  <div className="w-20 h-20 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mx-auto mb-4">
                    <span className="text-3xl">🏢</span>
                  </div>
                  <div className="text-white font-medium">Your System</div>
                  <div className="text-white/40 text-sm">Takes action</div>
                </div>
              </div>

              <div className="mt-8 pt-8 border-t border-white/10 text-center">
                <p className="text-white/50">
                  Documents never leave your infrastructure. PreFlight only sees metadata.
                </p>
              </div>
            </div>
          </div>

          {/* Compliance Section */}
          <div className="mb-20">
            <h2 className="text-2xl font-bold text-white mb-8 text-center">
              Compliance
            </h2>
            <div className="grid md:grid-cols-3 gap-6">
              <div className="bg-white/[0.02] rounded-xl border border-white/10 p-6 text-center">
                <div className="text-4xl mb-4">🏛️</div>
                <h3 className="text-lg font-bold text-white mb-2">SOC 2 Type II</h3>
                <p className="text-white/50 text-sm">Annual third-party security audit</p>
                <div className="mt-4 inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="text-emerald-400 text-xs">Compliant</span>
                </div>
              </div>
              <div className="bg-white/[0.02] rounded-xl border border-white/10 p-6 text-center">
                <div className="text-4xl mb-4">🇪🇺</div>
                <h3 className="text-lg font-bold text-white mb-2">GDPR Ready</h3>
                <p className="text-white/50 text-sm">No PII processing, EU hosting available</p>
                <div className="mt-4 inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="text-emerald-400 text-xs">Ready</span>
                </div>
              </div>
              <div className="bg-white/[0.02] rounded-xl border border-white/10 p-6 text-center">
                <div className="text-4xl mb-4">🏥</div>
                <h3 className="text-lg font-bold text-white mb-2">HIPAA Compatible</h3>
                <p className="text-white/50 text-sm">No PHI access = no BAA required</p>
                <div className="mt-4 inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="text-emerald-400 text-xs">Compatible</span>
                </div>
              </div>
            </div>
          </div>

          {/* CTA */}
          <div className="text-center p-12 bg-gradient-to-b from-emerald-500/10 to-transparent rounded-3xl border border-emerald-500/20">
            <h2 className="text-2xl md:text-3xl font-bold text-white mb-4">
              Questions about security?
            </h2>
            <p className="text-white/50 mb-8">
              Our team is happy to discuss your specific compliance requirements.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <a
                href="mailto:security@preflight.dev"
                className="inline-flex items-center justify-center gap-2 bg-white text-black px-8 py-4 rounded-full text-lg font-medium hover:bg-white/90 transition-all"
              >
                Contact Security Team
              </a>
              <Link
                href="/faq"
                className="inline-flex items-center justify-center gap-2 bg-white/5 text-white px-8 py-4 rounded-full text-lg font-medium hover:bg-white/10 transition-all border border-white/10"
              >
                Read FAQ
              </Link>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
