"use client";

import { useState, ReactNode } from "react";

// Mock data
const mockEvaluations = [
  {
    id: "eval-8834",
    correlationId: "invoice-8834",
    decision: "MATCH" as const,
    drift: 0.04,
    reliability: 0.92,
    template: "INV-ACME-001",
    extractor: "textract",
    timestamp: "2024-01-15 14:32:15",
  },
  {
    id: "eval-9921",
    correlationId: "receipt-9921",
    decision: "REVIEW" as const,
    drift: 0.34,
    reliability: 0.71,
    template: "RCP-VENDOR-02",
    extractor: "textract",
    timestamp: "2024-01-15 14:28:45",
  },
  {
    id: "eval-1234",
    correlationId: "contract-123",
    decision: "NEW" as const,
    drift: 0.89,
    reliability: 0.45,
    template: null,
    extractor: "azure",
    timestamp: "2024-01-15 14:25:12",
  },
  {
    id: "eval-5567",
    correlationId: "invoice-5567",
    decision: "MATCH" as const,
    drift: 0.06,
    reliability: 0.94,
    template: "INV-ACME-001",
    extractor: "textract",
    timestamp: "2024-01-15 14:22:08",
  },
  {
    id: "eval-7788",
    correlationId: "receipt-7788",
    decision: "REJECT" as const,
    drift: 0.78,
    reliability: 0.23,
    template: "RCP-OLD-01",
    extractor: "textract",
    timestamp: "2024-01-15 14:18:33",
  },
  {
    id: "eval-4455",
    correlationId: "invoice-4455",
    decision: "MATCH" as const,
    drift: 0.09,
    reliability: 0.91,
    template: "INV-ACME-001",
    extractor: "textract",
    timestamp: "2024-01-15 14:15:22",
  },
  {
    id: "eval-3322",
    correlationId: "contract-332",
    decision: "REVIEW" as const,
    drift: 0.28,
    reliability: 0.76,
    template: "CON-LEGAL-01",
    extractor: "azure",
    timestamp: "2024-01-15 14:12:18",
  },
];

type Decision = "ALL" | "MATCH" | "REVIEW" | "NEW" | "REJECT";

// Card component
function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`bg-white/[0.02] border border-white/5 rounded-2xl p-6 ${className}`}>
      {children}
    </div>
  );
}

// Decision badge
function DecisionBadge({ decision }: { decision: "MATCH" | "REVIEW" | "NEW" | "REJECT" }) {
  const styles = {
    MATCH: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    REVIEW: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    NEW: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
    REJECT: "bg-red-500/10 text-red-400 border-red-500/20",
  };

  return (
    <span className={`px-2 py-0.5 rounded-md text-xs font-medium border ${styles[decision]}`}>
      {decision}
    </span>
  );
}

// Icons
const Icons = {
  search: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  ),
  download: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
    </svg>
  ),
  chevronLeft: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 19l-7-7 7-7" />
    </svg>
  ),
  chevronRight: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5l7 7-7 7" />
    </svg>
  ),
};

export default function EvaluationsPage() {
  const [search, setSearch] = useState("");
  const [decisionFilter, setDecisionFilter] = useState<Decision>("ALL");

  const filteredEvaluations = mockEvaluations.filter((e) => {
    const matchesSearch =
      search === "" ||
      e.correlationId.toLowerCase().includes(search.toLowerCase()) ||
      e.id.toLowerCase().includes(search.toLowerCase());
    const matchesDecision =
      decisionFilter === "ALL" || e.decision === decisionFilter;
    return matchesSearch && matchesDecision;
  });

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Evaluations</h1>
          <p className="text-white/40 mt-1">Browse and filter your evaluation history</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="inline-flex items-center gap-2 px-3 py-2 text-sm text-white/60 hover:text-white border border-white/10 hover:border-white/20 rounded-lg transition-colors">
            {Icons.download}
            <span>CSV</span>
          </button>
          <button className="inline-flex items-center gap-2 px-3 py-2 text-sm text-white/60 hover:text-white border border-white/10 hover:border-white/20 rounded-lg transition-colors">
            {Icons.download}
            <span>JSON</span>
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30">
            {Icons.search}
          </div>
          <input
            type="text"
            placeholder="Search by ID or correlation ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-white/[0.02] border border-white/10 rounded-xl px-10 py-2.5 text-white placeholder-white/30 focus:outline-none focus:border-emerald-500/50 transition-colors"
          />
        </div>
        <div className="flex gap-2">
          {(["ALL", "MATCH", "REVIEW", "NEW", "REJECT"] as Decision[]).map((decision) => (
            <button
              key={decision}
              onClick={() => setDecisionFilter(decision)}
              className={`px-4 py-2.5 text-sm font-medium rounded-xl transition-colors ${
                decisionFilter === decision
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : "text-white/50 hover:text-white border border-white/10 hover:border-white/20"
              }`}
            >
              {decision}
            </button>
          ))}
        </div>
      </div>

      {/* Results Table */}
      <Card className="overflow-hidden p-0">
        <div className="px-6 py-4 border-b border-white/5">
          <h3 className="text-lg font-medium text-white">
            Results ({filteredEvaluations.length})
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-xs text-white/30 border-b border-white/5">
                <th className="px-6 py-3 font-medium">Evaluation ID</th>
                <th className="px-6 py-3 font-medium">Correlation ID</th>
                <th className="px-6 py-3 font-medium">Decision</th>
                <th className="px-6 py-3 font-medium">Drift</th>
                <th className="px-6 py-3 font-medium">Reliability</th>
                <th className="px-6 py-3 font-medium">Template</th>
                <th className="px-6 py-3 font-medium">Extractor</th>
                <th className="px-6 py-3 font-medium">Timestamp</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {filteredEvaluations.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-12 text-center text-white/30">
                    No evaluations match your filters
                  </td>
                </tr>
              ) : (
                filteredEvaluations.map((eval_) => (
                  <tr
                    key={eval_.id}
                    className="border-b border-white/5 hover:bg-white/[0.02] cursor-pointer transition-colors"
                    onClick={() => console.log("View evaluation:", eval_.id)}
                  >
                    <td className="px-6 py-4 text-white/50 font-mono text-xs">{eval_.id}</td>
                    <td className="px-6 py-4 text-white/70">{eval_.correlationId}</td>
                    <td className="px-6 py-4">
                      <DecisionBadge decision={eval_.decision} />
                    </td>
                    <td className={`px-6 py-4 ${
                      eval_.drift > 0.3 ? "text-red-400" : eval_.drift > 0.15 ? "text-amber-400" : "text-emerald-400"
                    }`}>
                      {eval_.drift.toFixed(2)}
                    </td>
                    <td className={`px-6 py-4 ${
                      eval_.reliability < 0.5 ? "text-red-400" : eval_.reliability < 0.8 ? "text-amber-400" : "text-emerald-400"
                    }`}>
                      {eval_.reliability.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 text-white/50 font-mono text-xs">
                      {eval_.template || <span className="text-white/20">-</span>}
                    </td>
                    <td className="px-6 py-4 text-white/40">{eval_.extractor}</td>
                    <td className="px-6 py-4 text-white/30">{eval_.timestamp}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-white/40">
          Showing {filteredEvaluations.length} of {mockEvaluations.length} evaluations
        </span>
        <div className="flex items-center gap-2">
          <button
            disabled
            className="inline-flex items-center gap-1 px-3 py-2 text-sm text-white/30 border border-white/10 rounded-lg cursor-not-allowed"
          >
            {Icons.chevronLeft}
            <span>Previous</span>
          </button>
          <span className="px-4 py-2 text-sm text-white/40">Page 1 of 1</span>
          <button
            disabled
            className="inline-flex items-center gap-1 px-3 py-2 text-sm text-white/30 border border-white/10 rounded-lg cursor-not-allowed"
          >
            <span>Next</span>
            {Icons.chevronRight}
          </button>
        </div>
      </div>
    </div>
  );
}
