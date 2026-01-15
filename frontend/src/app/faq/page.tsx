"use client";

import { useState } from "react";
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
          <Link href="/#pricing" className="text-white/60 hover:text-white transition-colors text-sm">
            Pricing
          </Link>
          <Link href="/faq" className="text-white transition-colors text-sm">
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

// Collapsible FAQ item
function FAQItem({ question, answer, isOpen, onClick }: {
  question: string;
  answer: React.ReactNode;
  isOpen: boolean;
  onClick: () => void;
}) {
  return (
    <div className="border-b border-white/10">
      <button
        onClick={onClick}
        className="w-full py-6 flex items-center justify-between text-left group"
      >
        <span className="text-lg text-white/90 group-hover:text-white transition-colors pr-8">
          {question}
        </span>
        <span className={`text-white/40 transition-transform duration-200 ${isOpen ? 'rotate-45' : ''}`}>
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </span>
      </button>
      <div className={`overflow-hidden transition-all duration-300 ${isOpen ? 'max-h-[500px] pb-6' : 'max-h-0'}`}>
        <div className="text-white/50 leading-relaxed">
          {answer}
        </div>
      </div>
    </div>
  );
}

// FAQ Section with category header
function FAQSection({ title, icon, items }: {
  title: string;
  icon: string;
  items: { question: string; answer: React.ReactNode }[];
}) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <div className="mb-16">
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center text-lg">
          {icon}
        </div>
        <h2 className="text-2xl font-bold text-white">{title}</h2>
      </div>
      <div className="bg-white/[0.02] rounded-2xl border border-white/10 px-8">
        {items.map((item, index) => (
          <FAQItem
            key={index}
            question={item.question}
            answer={item.answer}
            isOpen={openIndex === index}
            onClick={() => setOpenIndex(openIndex === index ? null : index)}
          />
        ))}
      </div>
    </div>
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
            <Link href="/#pricing" className="hover:text-white transition-colors">Pricing</Link>
            <Link href="/privacy" className="hover:text-white transition-colors">Privacy</Link>
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

export default function FAQPage() {
  const privacyFAQ = [
    {
      question: "How can you guarantee you're not reading our documents?",
      answer: (
        <div className="space-y-4">
          <p>
            We literally can&apos;t read your documents. Our API only accepts metadata&mdash;bounding boxes,
            element counts, confidence scores. We never receive images, PDFs, or extracted text.
          </p>
          <p>
            It&apos;s architecturally impossible for us to see your documents. You can verify this by
            inspecting our API contract&mdash;there&apos;s no field for document content.
          </p>
          <div className="bg-[#0d0d0d] rounded-xl p-4 mt-4 font-mono text-sm">
            <div className="text-white/40 mb-2">{/* What we receive: */}What we receive:</div>
            <div className="text-emerald-400">
              {"{"} element_count: <span className="text-white">45</span>,
              table_count: <span className="text-white">2</span>,
              bounding_boxes: <span className="text-white">[...]</span> {"}"}
            </div>
            <div className="text-white/40 mt-2">What we NEVER receive: document images, text, values, PII</div>
          </div>
        </div>
      )
    },
    {
      question: "What data do you actually receive?",
      answer: (
        <div className="space-y-3">
          <p>Only structural fingerprints:</p>
          <ul className="space-y-2 ml-4">
            <li className="flex items-start gap-2">
              <span className="text-emerald-400 mt-1">+</span>
              <span>How many tables, text blocks, and images are on the page</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-emerald-400 mt-1">+</span>
              <span>Where elements are positioned (bounding boxes as coordinates)</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-emerald-400 mt-1">+</span>
              <span>What confidence your extractor reported</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-emerald-400 mt-1">+</span>
              <span>Layout complexity and structure metrics</span>
            </li>
          </ul>
          <p className="mt-4 text-white/70 font-medium">
            Never the content itself&mdash;not the words, not the values, not the images.
          </p>
        </div>
      )
    },
    {
      question: "Can you prove this?",
      answer: (
        <div className="space-y-3">
          <p>Yes. Three ways:</p>
          <ol className="space-y-3 ml-4">
            <li className="flex items-start gap-3">
              <span className="text-emerald-400 font-bold">1.</span>
              <div>
                <span className="text-white/80 font-medium">Our API schema</span>
                <span className="text-white/50">&mdash;no content fields exist. Review our OpenAPI spec.</span>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <span className="text-emerald-400 font-bold">2.</span>
              <div>
                <span className="text-white/80 font-medium">Request logging</span>
                <span className="text-white/50">&mdash;you can audit exactly what you send us.</span>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <span className="text-emerald-400 font-bold">3.</span>
              <div>
                <span className="text-white/80 font-medium">SOC 2 Type II audit</span>
                <span className="text-white/50">&mdash;third-party verification of our security controls.</span>
              </div>
            </li>
          </ol>
        </div>
      )
    }
  ];

  const howItWorksFAQ = [
    {
      question: "How does it work if you can't see the documents?",
      answer: (
        <div className="space-y-4">
          <p>
            Document structure is surprisingly consistent. An invoice from ACME Corp always has tables
            in the same place, the same number of text blocks, similar layout.
          </p>
          <p>
            We learn that <span className="text-emerald-400 font-medium">fingerprint</span>. When we see
            it again, we know which correction rules to apply&mdash;without ever seeing what&apos;s written.
          </p>
          <p>
            Think of it like recognizing a form by its shape, not by reading it.
          </p>
        </div>
      )
    },
    {
      question: "What if my extractor makes a mistake?",
      answer: (
        <div className="space-y-4">
          <p>
            That&apos;s exactly what we catch. If your extractor&apos;s confidence drops, or the document
            structure drifts from the template, we flag it for review <span className="text-emerald-400 font-medium">before</span> it
            causes downstream errors.
          </p>
          <p>
            Our drift detection catches degradation in extraction quality over time&mdash;even when the
            extractor itself doesn&apos;t report low confidence.
          </p>
        </div>
      )
    },
    {
      question: "What extractors do you support?",
      answer: (
        <div className="space-y-3">
          <p>PreFlight works with any document extraction service:</p>
          <div className="flex flex-wrap gap-3 mt-4">
            {["AWS Textract", "Azure Form Recognizer", "Google Document AI", "NVIDIA NeMo", "ABBYY", "Tesseract", "Custom OCR"].map((provider) => (
              <span key={provider} className="px-3 py-1 bg-white/5 rounded-full text-sm text-white/70 border border-white/10">
                {provider}
              </span>
            ))}
          </div>
          <p className="mt-4">
            If your extractor can output bounding boxes and confidence scores, it works with PreFlight.
          </p>
        </div>
      )
    }
  ];

  const valueFAQ = [
    {
      question: "How do I know this is actually saving me time?",
      answer: (
        <div className="space-y-4">
          <p>Dashboard metrics show:</p>
          <ul className="space-y-2 ml-4">
            <li className="flex items-start gap-2">
              <span className="text-emerald-400 mt-1">+</span>
              <span>Documents auto-processed vs flagged for review</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-emerald-400 mt-1">+</span>
              <span>Drift score trends (catching degradation early)</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-emerald-400 mt-1">+</span>
              <span>Estimated errors prevented based on reliability thresholds</span>
            </li>
          </ul>
          <p className="mt-4 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl">
            Most clients see <span className="text-emerald-400 font-bold">60-80%</span> of documents
            auto-approved with high confidence, reducing manual review burden significantly.
          </p>
        </div>
      )
    },
    {
      question: "What's the ROI?",
      answer: (
        <div className="space-y-4">
          <p>
            One bad extraction that makes it to production can cost hours of cleanup, customer complaints,
            or compliance issues.
          </p>
          <p>
            PreFlight catches those before they happen. The math usually works after preventing
            <span className="text-emerald-400 font-medium"> 1-2 incidents</span> that would have
            required manual intervention.
          </p>
          <p>
            For teams processing thousands of documents monthly, the time saved on manual QA alone
            typically exceeds the subscription cost.
          </p>
        </div>
      )
    }
  ];

  const technicalFAQ = [
    {
      question: "How fast is it? Will it slow down my pipeline?",
      answer: (
        <div className="space-y-4">
          <p className="flex items-center gap-3">
            <span className="text-3xl font-bold text-emerald-400">~11ms</span>
            <span>average response time</span>
          </p>
          <p>
            We&apos;re a metadata check, not a processing step. Your pipeline calls us, gets a decision,
            and continues. Real-time, no batching required.
          </p>
          <p className="text-white/70">
            For comparison, your OCR extraction likely takes 500ms-2s. Our 11ms is negligible overhead.
          </p>
        </div>
      )
    },
    {
      question: "What if PreFlight is down?",
      answer: (
        <div className="space-y-4">
          <p>
            We recommend <span className="text-emerald-400 font-medium">fail-open with logging</span>.
            If we&apos;re unreachable, process normally but flag for later review.
          </p>
          <p>
            Our infrastructure is designed for high availability with 99.9% uptime SLA. We use
            redundant deployments across multiple availability zones.
          </p>
        </div>
      )
    },
    {
      question: "How do I integrate PreFlight?",
      answer: (
        <div className="space-y-4">
          <p>One API call after your existing extraction:</p>
          <div className="bg-[#0d0d0d] rounded-xl p-4 mt-4 font-mono text-sm">
            <div className="text-white/40">{`# After your existing OCR call`}</div>
            <div>
              <span className="text-cyan-400">response</span>
              <span className="text-white"> = </span>
              <span className="text-amber-400">preflight</span>
              <span className="text-white">.evaluate(</span>
              <span className="text-emerald-400">extraction_result</span>
              <span className="text-white">)</span>
            </div>
            <div className="mt-2" />
            <div className="text-white/40">{`# Use the decision in your pipeline`}</div>
            <div>
              <span className="text-cyan-400">if</span>
              <span className="text-white"> response.decision == </span>
              <span className="text-emerald-400">&quot;MATCH&quot;</span>
              <span className="text-white">:</span>
            </div>
            <div className="pl-4 text-white">auto_process()</div>
            <div>
              <span className="text-cyan-400">else</span>
              <span className="text-white">:</span>
            </div>
            <div className="pl-4 text-white">send_to_review_queue()</div>
          </div>
          <p className="mt-4">
            SDKs available for Python, Node.js, and REST API for any language.
          </p>
        </div>
      )
    }
  ];

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      <Header />

      <main className="pt-32 pb-20 px-6">
        <div className="max-w-4xl mx-auto">
          {/* Hero */}
          <div className="text-center mb-20">
            <h1 className="text-4xl md:text-6xl font-bold text-white mb-6">
              Frequently Asked Questions
            </h1>
            <p className="text-xl text-white/50 max-w-2xl mx-auto">
              Everything you need to know about PreFlight and how it protects your
              document extraction pipeline.
            </p>
          </div>

          {/* FAQ Sections */}
          <FAQSection
            title="Privacy & Security"
            icon="🔒"
            items={privacyFAQ}
          />

          <FAQSection
            title="How It Works"
            icon="⚡"
            items={howItWorksFAQ}
          />

          <FAQSection
            title="Value & ROI"
            icon="📈"
            items={valueFAQ}
          />

          <FAQSection
            title="Technical"
            icon="🔧"
            items={technicalFAQ}
          />

          {/* CTA */}
          <div className="text-center mt-20 p-12 bg-gradient-to-b from-emerald-500/10 to-transparent rounded-3xl border border-emerald-500/20">
            <h2 className="text-2xl md:text-3xl font-bold text-white mb-4">
              Still have questions?
            </h2>
            <p className="text-white/50 mb-8">
              We&apos;re happy to walk you through how PreFlight can work for your specific use case.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                href="/signup"
                className="inline-flex items-center justify-center gap-2 bg-white text-black px-8 py-4 rounded-full text-lg font-medium hover:bg-white/90 transition-all"
              >
                Start Free Trial
              </Link>
              <a
                href="mailto:hello@preflight.dev"
                className="inline-flex items-center justify-center gap-2 bg-white/5 text-white px-8 py-4 rounded-full text-lg font-medium hover:bg-white/10 transition-all border border-white/10"
              >
                Contact Us
              </a>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
