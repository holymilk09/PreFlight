"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { AnimatedCounter } from "@/components/ui";

// Minimal header for enterprise
function Header() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 50);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? "bg-[#0a0a0a]/95 backdrop-blur-md border-b border-white/5"
          : "bg-transparent"
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <Link href="/" className="text-white font-medium text-xl tracking-tight">
          PreFlight
        </Link>
        <nav className="hidden md:flex items-center gap-8">
          <Link href="#product" className="text-white/60 hover:text-white transition-colors text-sm">
            Product
          </Link>
          <Link href="#how-it-works" className="text-white/60 hover:text-white transition-colors text-sm">
            How It Works
          </Link>
          <Link href="#pricing" className="text-white/60 hover:text-white transition-colors text-sm">
            Pricing
          </Link>
          <Link href="/faq" className="text-white/60 hover:text-white transition-colors text-sm">
            FAQ
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

// Hero section - Apple-like with big statement
function Hero() {
  return (
    <section className="min-h-screen flex flex-col justify-center px-6 pt-20 relative overflow-hidden">
      {/* Subtle gradient background */}
      <div className="absolute inset-0 bg-gradient-to-b from-emerald-950/20 via-transparent to-transparent" />

      {/* Animated grid lines */}
      <div className="absolute inset-0 opacity-[0.02]">
        <div className="absolute inset-0" style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
                           linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
          backgroundSize: '60px 60px'
        }} />
      </div>

      <div className="max-w-7xl mx-auto w-full relative z-10">
        <div className="max-w-4xl">
          {/* Small label */}
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 mb-8">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-emerald-400 text-sm font-medium">Document Intelligence Platform</span>
          </div>

          {/* Main headline */}
          <h1 className="text-5xl md:text-7xl lg:text-8xl font-bold text-white leading-[0.9] tracking-tight mb-8">
            Know when your
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-cyan-400">
              extraction drifts.
            </span>
          </h1>

          {/* Subheadline */}
          <p className="text-xl md:text-2xl text-white/50 max-w-2xl mb-12 leading-relaxed">
            The control plane for document extraction pipelines.
            Detect drift, ensure reliability, maintain compliance—without ever touching your documents.
          </p>

          {/* CTA buttons */}
          <div className="flex flex-col sm:flex-row gap-4 mb-16">
            <Link
              href="/signup"
              className="inline-flex items-center justify-center gap-2 bg-white text-black px-8 py-4 rounded-full text-lg font-medium hover:bg-white/90 transition-all hover:scale-[1.02]"
            >
              Start Free Trial
              <span className="text-black/40">→</span>
            </Link>
            <Link
              href="#how-it-works"
              className="inline-flex items-center justify-center gap-2 bg-white/5 text-white px-8 py-4 rounded-full text-lg font-medium hover:bg-white/10 transition-all border border-white/10"
            >
              See How It Works
            </Link>
          </div>

          {/* Trust indicators */}
          <div className="flex flex-wrap gap-8 text-white/30 text-sm">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
              SOC 2 Type II
            </div>
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
              Zero Document Access
            </div>
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              {"<"}15ms Response
            </div>
          </div>
        </div>
      </div>

      {/* Scroll indicator */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2">
        <div className="w-6 h-10 rounded-full border-2 border-white/20 flex items-start justify-center p-2">
          <div className="w-1 h-2 bg-white/40 rounded-full animate-bounce" />
        </div>
      </div>
    </section>
  );
}

// Product visualization - the actual system
function ProductVisualization() {
  return (
    <section id="product" className="py-32 px-6 relative">
      <div className="max-w-7xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-20">
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
            See everything. Touch nothing.
          </h2>
          <p className="text-xl text-white/50 max-w-2xl mx-auto">
            PreFlight analyzes structural metadata from your extraction pipeline—never the documents themselves.
          </p>
        </div>

        {/* Main product visualization */}
        <div className="relative bg-gradient-to-b from-white/[0.03] to-transparent rounded-3xl border border-white/10 p-8 md:p-12">
          {/* The flow diagram */}
          <div className="grid md:grid-cols-5 gap-4 md:gap-8 items-center">
            {/* Source Documents */}
            <div className="text-center">
              <div className="bg-white/5 rounded-2xl p-6 mb-4 border border-white/10">
                <div className="text-4xl mb-2">📄</div>
                <div className="space-y-1">
                  <div className="h-2 bg-white/20 rounded w-full" />
                  <div className="h-2 bg-white/10 rounded w-3/4 mx-auto" />
                  <div className="h-2 bg-white/10 rounded w-5/6 mx-auto" />
                </div>
              </div>
              <div className="text-white/60 text-sm font-medium">Your Documents</div>
              <div className="text-white/30 text-xs mt-1">PDFs, Images, Scans</div>
            </div>

            {/* Arrow */}
            <div className="hidden md:flex items-center justify-center">
              <div className="flex items-center gap-2 text-white/20">
                <div className="h-px w-full bg-gradient-to-r from-white/20 to-white/5" />
                <span className="text-xs whitespace-nowrap">OCR</span>
                <div className="h-px w-full bg-gradient-to-r from-white/5 to-white/20" />
              </div>
            </div>

            {/* Your Extractor */}
            <div className="text-center">
              <div className="bg-white/5 rounded-2xl p-6 mb-4 border border-white/10">
                <div className="text-4xl mb-2">⚙️</div>
                <div className="text-xs text-white/40 font-mono">
                  Textract / Azure
                  <br />
                  Google / Custom
                </div>
              </div>
              <div className="text-white/60 text-sm font-medium">Your Extractor</div>
              <div className="text-white/30 text-xs mt-1">Any OCR Provider</div>
            </div>

            {/* Arrow with "Metadata Only" label */}
            <div className="hidden md:flex items-center justify-center">
              <div className="flex flex-col items-center gap-1">
                <div className="flex items-center gap-2 text-emerald-400/60">
                  <div className="h-px w-8 bg-gradient-to-r from-emerald-400/20 to-emerald-400/60" />
                  <span className="text-xs whitespace-nowrap font-medium">Metadata Only</span>
                  <div className="h-px w-8 bg-gradient-to-r from-emerald-400/60 to-emerald-400/20" />
                </div>
                <div className="text-[10px] text-white/30">No content sent</div>
              </div>
            </div>

            {/* PreFlight */}
            <div className="text-center">
              <div className="bg-gradient-to-b from-emerald-500/20 to-emerald-500/5 rounded-2xl p-6 mb-4 border border-emerald-500/30 relative">
                <div className="absolute -top-2 -right-2 w-4 h-4 bg-emerald-500 rounded-full animate-pulse" />
                <div className="text-2xl font-bold text-emerald-400 mb-2">PreFlight</div>
                <div className="space-y-2 text-left text-xs">
                  <div className="flex justify-between">
                    <span className="text-white/40">Template:</span>
                    <span className="text-white/80 font-mono">INV-2024-A</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/40">Drift:</span>
                    <span className="text-emerald-400 font-mono">0.04</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/40">Reliability:</span>
                    <span className="text-emerald-400 font-mono">0.96</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/40">Decision:</span>
                    <span className="text-emerald-400 font-mono">MATCH</span>
                  </div>
                </div>
              </div>
              <div className="text-emerald-400 text-sm font-medium">PreFlight</div>
              <div className="text-white/30 text-xs mt-1">Control Plane</div>
            </div>
          </div>

          {/* What we receive vs what we never see */}
          <div className="grid md:grid-cols-2 gap-8 mt-16 pt-12 border-t border-white/5">
            <div>
              <div className="flex items-center gap-2 mb-4">
                <div className="w-2 h-2 rounded-full bg-emerald-500" />
                <span className="text-white/60 text-sm font-medium">What We Analyze</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {["Bounding boxes", "Element types", "Layout structure", "Confidence scores", "Field positions", "Page geometry"].map((item) => (
                  <div key={item} className="flex items-center gap-2 text-white/40 text-sm">
                    <span className="text-emerald-500">+</span>
                    {item}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2 mb-4">
                <div className="w-2 h-2 rounded-full bg-red-500" />
                <span className="text-white/60 text-sm font-medium">What We Never See</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {["Document images", "Extracted text", "Field values", "PII / PHI", "File contents", "Sensitive data"].map((item) => (
                  <div key={item} className="flex items-center gap-2 text-white/40 text-sm">
                    <span className="text-red-500">×</span>
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// Value props with big numbers
function ValueProps() {
  const stats = [
    {
      value: 73,
      suffix: "%",
      label: "Reduction in extraction errors",
      description: "Catch drift before it causes downstream failures"
    },
    {
      value: 4.2,
      suffix: "hrs",
      label: "Saved per week per engineer",
      description: "Automated monitoring replaces manual QA checks"
    },
    {
      value: 99.7,
      suffix: "%",
      label: "Pipeline reliability",
      description: "Confidence scoring prevents bad data from entering your systems"
    }
  ];

  return (
    <section className="py-32 px-6 bg-gradient-to-b from-transparent via-emerald-950/10 to-transparent">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-20">
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
            The ROI is immediate.
          </h2>
          <p className="text-xl text-white/50 max-w-2xl mx-auto">
            Teams using PreFlight see measurable improvements within the first week.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {stats.map((stat, i) => (
            <div key={i} className="text-center p-8 rounded-3xl bg-white/[0.02] border border-white/5 hover:border-white/10 transition-colors">
              <div className="text-6xl md:text-7xl font-bold text-white mb-2">
                <AnimatedCounter value={stat.value} suffix={stat.suffix} decimals={stat.value % 1 !== 0 ? 1 : 0} duration={2000} />
              </div>
              <div className="text-white/80 font-medium mb-2">{stat.label}</div>
              <div className="text-white/40 text-sm">{stat.description}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// How it works - step by step
function HowItWorks() {
  const steps = [
    {
      num: "01",
      title: "Connect your extractor",
      description: "Install our lightweight SDK and add one line after your existing OCR call. Works with AWS Textract, Azure Form Recognizer, Google Document AI, or any custom solution.",
      code: `result = pf.evaluate(extraction_response)`
    },
    {
      num: "02",
      title: "Templates emerge automatically",
      description: "Similar document structures cluster into templates based on layout fingerprints alone. No manual training, no content analysis—just geometry.",
      visual: "auto-learning"
    },
    {
      num: "03",
      title: "Bad data never gets through",
      description: "Every extraction returns with a reliability verdict in milliseconds. Your system reads the decision and acts—auto-processing high-confidence results, routing low-confidence ones to your existing review queue. The logic lives in PreFlight; the action happens in your pipeline.",
      visual: "drift-alert"
    },
    {
      num: "04",
      title: "Your pipeline self-corrects",
      description: "High-confidence extractions flow through automatically. Anomalies route to review queues. Templates adapt to legitimate format changes. Continuous improvement, zero manual intervention.",
      visual: "routing"
    }
  ];

  return (
    <section id="how-it-works" className="py-32 px-6">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-20">
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
            Four steps to reliable extraction.
          </h2>
          <p className="text-xl text-white/50 max-w-2xl mx-auto">
            From integration to production insights in under 5 minutes.
          </p>
        </div>

        <div className="space-y-24">
          {steps.map((step, i) => (
            <div key={step.num} className={`grid md:grid-cols-2 gap-12 items-center ${i % 2 === 1 ? 'md:grid-flow-dense' : ''}`}>
              <div className={i % 2 === 1 ? 'md:col-start-2' : ''}>
                <div className="text-emerald-400/60 text-sm font-mono mb-4">{step.num}</div>
                <h3 className="text-3xl font-bold text-white mb-4">{step.title}</h3>
                <p className="text-white/50 text-lg leading-relaxed">{step.description}</p>
                {step.code && (
                  <div className="mt-6 bg-[#0d0d0d] rounded-xl p-4 border border-white/10 font-mono text-sm">
                    <span className="text-white/40"># After your existing OCR</span>
                    <br />
                    <span className="text-emerald-400">{step.code}</span>
                  </div>
                )}
              </div>
              <div className={i % 2 === 1 ? 'md:col-start-1 md:row-start-1' : ''}>
                {/* Visual for each step */}
                <div className="bg-white/[0.02] rounded-2xl border border-white/10 p-8 aspect-[4/3] flex items-center justify-center">
                  {step.num === "01" && (
                    <div className="text-center">
                      <div className="flex justify-center gap-4 mb-6">
                        {["AWS", "Azure", "Google", "Custom"].map((provider) => (
                          <div key={provider} className="w-16 h-16 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-white/40 text-xs">
                            {provider}
                          </div>
                        ))}
                      </div>
                      <div className="text-white/40 text-sm">Connects to any extraction provider</div>
                    </div>
                  )}
                  {step.num === "02" && (
                    <div className="space-y-4 w-full max-w-sm">
                      {[
                        { name: "Invoice A", count: 1247, color: "emerald" },
                        { name: "Receipt B", count: 892, color: "cyan" },
                        { name: "Contract C", count: 456, color: "amber" }
                      ].map((template) => (
                        <div key={template.name} className="flex items-center gap-4 bg-white/5 rounded-lg p-3">
                          <div className={`w-3 h-3 rounded-full bg-${template.color}-500`} />
                          <div className="flex-1 text-white/60 text-sm">{template.name}</div>
                          <div className="text-white/40 text-xs font-mono">{template.count} docs</div>
                        </div>
                      ))}
                    </div>
                  )}
                  {step.num === "03" && (
                    <div className="w-full max-w-md font-mono text-xs">
                      <div className="text-white/40 text-sm mb-4 text-center font-sans">API Response → Your System Acts</div>
                      <div className="space-y-3">
                        {/* High confidence - auto process */}
                        <div className="bg-white/5 rounded-lg p-3 border border-white/10">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-white/30">invoice.pdf</span>
                            <span className="text-white/20">→</span>
                            <span className="text-emerald-400/80">PreFlight</span>
                            <span className="text-white/20">→</span>
                          </div>
                          <div className="pl-4 text-emerald-400">
                            {"{"} decision: <span className="text-white">&quot;MATCH&quot;</span>, reliability: <span className="text-white">0.94</span> {"}"}
                          </div>
                          <div className="pl-4 mt-1 text-emerald-400/60">
                            → your system auto-processes ✓
                          </div>
                        </div>
                        {/* Low confidence - held */}
                        <div className="bg-white/5 rounded-lg p-3 border border-white/10">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-white/30">receipt.pdf</span>
                            <span className="text-white/20">→</span>
                            <span className="text-amber-400/80">PreFlight</span>
                            <span className="text-white/20">→</span>
                          </div>
                          <div className="pl-4 text-amber-400">
                            {"{"} decision: <span className="text-white">&quot;REVIEW&quot;</span>, reliability: <span className="text-white">0.67</span> {"}"}
                          </div>
                          <div className="pl-4 mt-1 text-amber-400/60">
                            → your system routes to review queue ⏸
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                  {step.num === "04" && (
                    <div className="space-y-3 w-full max-w-sm">
                      <div className="flex items-center gap-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-3">
                        <span className="text-emerald-400 text-sm">✓ MATCH</span>
                        <span className="text-white/40 text-xs flex-1">→ Auto-process</span>
                        <span className="text-emerald-400/60 text-xs">94%</span>
                      </div>
                      <div className="flex items-center gap-3 bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                        <span className="text-amber-400 text-sm">? REVIEW</span>
                        <span className="text-white/40 text-xs flex-1">→ Human queue</span>
                        <span className="text-amber-400/60 text-xs">5%</span>
                      </div>
                      <div className="flex items-center gap-3 bg-cyan-500/10 border border-cyan-500/30 rounded-lg p-3">
                        <span className="text-cyan-400 text-sm">+ NEW</span>
                        <span className="text-white/40 text-xs flex-1">→ Template creation</span>
                        <span className="text-cyan-400/60 text-xs">1%</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// Integration model clarification
function IntegrationModel() {
  return (
    <section className="py-32 px-6 bg-gradient-to-b from-white/[0.02] to-transparent">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
            Infrastructure, not another dashboard.
          </h2>
          <p className="text-xl text-white/50 max-w-2xl mx-auto">
            PreFlight is an API that powers your existing systems—not a destination your team has to check.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8">
          {/* Real-time API */}
          <div className="bg-white/[0.02] rounded-2xl border border-white/10 p-8">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center">
                <span className="text-emerald-400">⚡</span>
              </div>
              <h3 className="text-xl font-bold text-white">Real-time API</h3>
            </div>
            <p className="text-white/50 mb-6">
              Every extraction gets a verdict in milliseconds. Your pipeline reads the response and acts—no human in the loop for the 94% that pass.
            </p>
            <ul className="space-y-2 text-sm">
              <li className="flex items-center gap-2 text-white/60">
                <span className="text-emerald-400">→</span>
                Decisions return to your code instantly
              </li>
              <li className="flex items-center gap-2 text-white/60">
                <span className="text-emerald-400">→</span>
                Route to your existing review tools
              </li>
              <li className="flex items-center gap-2 text-white/60">
                <span className="text-emerald-400">→</span>
                Webhooks for alerts to Slack, PagerDuty, etc.
              </li>
            </ul>
          </div>

          {/* Dashboard for engineers */}
          <div className="bg-white/[0.02] rounded-2xl border border-white/10 p-8">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-cyan-500/20 flex items-center justify-center">
                <span className="text-cyan-400">📊</span>
              </div>
              <h3 className="text-xl font-bold text-white">Dashboard for Engineers</h3>
            </div>
            <p className="text-white/50 mb-6">
              Configure thresholds, manage templates, and view analytics. For engineering teams—not daily operators.
            </p>
            <ul className="space-y-2 text-sm">
              <li className="flex items-center gap-2 text-white/60">
                <span className="text-cyan-400">→</span>
                Template management and tuning
              </li>
              <li className="flex items-center gap-2 text-white/60">
                <span className="text-cyan-400">→</span>
                Drift trends and analytics over time
              </li>
              <li className="flex items-center gap-2 text-white/60">
                <span className="text-cyan-400">→</span>
                Audit logs for compliance
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-12 text-center">
          <p className="text-white/30 text-sm">
            Your operators stay in their existing tools. PreFlight works behind the scenes.
          </p>
        </div>
      </div>
    </section>
  );
}

// Social proof / testimonial
function SocialProof() {
  return (
    <section className="py-32 px-6 bg-gradient-to-b from-transparent to-white/[0.02]">
      <div className="max-w-4xl mx-auto text-center">
        <div className="text-6xl mb-8">&ldquo;</div>
        <blockquote className="text-2xl md:text-3xl text-white/80 font-light leading-relaxed mb-8">
          PreFlight caught a 40% drift in our invoice templates from a vendor format change.
          Without it, we would have processed 2,000 documents with incorrect field mappings
          before anyone noticed.
        </blockquote>
        <div className="text-white/40">
          <div className="font-medium text-white/60">Sarah Chen</div>
          <div className="text-sm">Director of Engineering, Fortune 500 Financial Services</div>
        </div>
      </div>
    </section>
  );
}

// Pricing section
function Pricing() {
  const tiers = [
    {
      name: "Starter",
      price: "$0",
      period: "forever",
      description: "For individual developers and small projects",
      features: [
        "1,000 evaluations/month",
        "5 templates",
        "7-day data retention",
        "Email support"
      ],
      cta: "Start Free",
      highlighted: false
    },
    {
      name: "Team",
      price: "$199",
      period: "/month",
      description: "For growing teams with production workloads",
      features: [
        "100,000 evaluations/month",
        "Unlimited templates",
        "90-day data retention",
        "Priority support",
        "Team management",
        "Audit logs",
        "Custom webhooks"
      ],
      cta: "Start Free Trial",
      highlighted: true
    },
    {
      name: "Enterprise",
      price: "Custom",
      period: "",
      description: "For organizations with compliance requirements",
      features: [
        "Unlimited evaluations",
        "Custom retention",
        "Dedicated support",
        "SSO / SAML",
        "On-premise option",
        "SLA guarantee",
        "Custom integrations"
      ],
      cta: "Contact Sales",
      highlighted: false
    }
  ];

  return (
    <section id="pricing" className="py-32 px-6">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-20">
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
            Simple, predictable pricing.
          </h2>
          <p className="text-xl text-white/50 max-w-2xl mx-auto">
            Start free, scale when you&apos;re ready. No surprises.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {tiers.map((tier) => (
            <div
              key={tier.name}
              className={`rounded-3xl p-8 ${
                tier.highlighted
                  ? 'bg-gradient-to-b from-emerald-500/20 to-emerald-500/5 border-2 border-emerald-500/30'
                  : 'bg-white/[0.02] border border-white/10'
              }`}
            >
              {tier.highlighted && (
                <div className="text-emerald-400 text-xs font-medium mb-4">MOST POPULAR</div>
              )}
              <div className="text-white text-xl font-medium mb-2">{tier.name}</div>
              <div className="flex items-baseline gap-1 mb-2">
                <span className="text-4xl font-bold text-white">{tier.price}</span>
                <span className="text-white/40">{tier.period}</span>
              </div>
              <p className="text-white/40 text-sm mb-8">{tier.description}</p>
              <ul className="space-y-3 mb-8">
                {tier.features.map((feature) => (
                  <li key={feature} className="flex items-center gap-3 text-white/60 text-sm">
                    <span className="text-emerald-400">✓</span>
                    {feature}
                  </li>
                ))}
              </ul>
              <Link
                href={tier.name === "Enterprise" ? "/contact" : "/signup"}
                className={`block text-center py-3 rounded-full font-medium transition-all ${
                  tier.highlighted
                    ? 'bg-white text-black hover:bg-white/90'
                    : 'bg-white/5 text-white hover:bg-white/10 border border-white/10'
                }`}
              >
                {tier.cta}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// Final CTA
function FinalCTA() {
  return (
    <section className="py-32 px-6">
      <div className="max-w-4xl mx-auto text-center">
        <h2 className="text-4xl md:text-6xl font-bold text-white mb-6">
          Ready to take control?
        </h2>
        <p className="text-xl text-white/50 mb-12 max-w-2xl mx-auto">
          Join hundreds of teams who trust PreFlight to govern their document extraction pipelines.
        </p>
        <Link
          href="/signup"
          className="inline-flex items-center gap-2 bg-white text-black px-12 py-5 rounded-full text-xl font-medium hover:bg-white/90 transition-all hover:scale-[1.02]"
        >
          Get Started Free
          <span className="text-black/40">→</span>
        </Link>
        <p className="text-white/30 text-sm mt-6">
          No credit card required · 1,000 free evaluations per month
        </p>
      </div>
    </section>
  );
}

// Minimal footer
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
            © {new Date().getFullYear()} PreFlight
          </div>
        </div>
      </div>
    </footer>
  );
}

export default function Home() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      <Header />
      <main>
        <Hero />
        <ProductVisualization />
        <ValueProps />
        <HowItWorks />
        <IntegrationModel />
        <SocialProof />
        <Pricing />
        <FinalCTA />
      </main>
      <Footer />
    </div>
  );
}
