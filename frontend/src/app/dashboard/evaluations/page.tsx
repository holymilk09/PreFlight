"use client";

import { useState } from "react";
import { Box, Button, Input, StatusBadge, Table } from "@/components/ui";

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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl text-terminal-white">Evaluations</h1>
          <p className="text-terminal-white-dim text-sm">
            Browse and filter your evaluation history
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm">
            [^] Export CSV
          </Button>
          <Button variant="secondary" size="sm">
            [J] Export JSON
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Box title="FILTERS">
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <Input
              placeholder="Search by ID or correlation ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            {(["ALL", "MATCH", "REVIEW", "NEW", "REJECT"] as Decision[]).map(
              (decision) => (
                <button
                  key={decision}
                  onClick={() => setDecisionFilter(decision)}
                  className={`px-3 py-2 text-sm transition-colors ${
                    decisionFilter === decision
                      ? "bg-terminal-green text-terminal-black"
                      : "text-terminal-white-dim hover:text-terminal-green border border-terminal-gray"
                  }`}
                >
                  {decision}
                </button>
              )
            )}
          </div>
        </div>
      </Box>

      {/* Results */}
      <Box title={`RESULTS (${filteredEvaluations.length})`}>
        <Table
          columns={[
            { key: "id", header: "Evaluation ID", width: "w-32" },
            { key: "correlationId", header: "Correlation ID" },
            {
              key: "decision",
              header: "Decision",
              render: (row) => <StatusBadge status={row.decision} />,
            },
            {
              key: "drift",
              header: "Drift",
              render: (row) => (
                <span
                  className={
                    row.drift > 0.3
                      ? "text-terminal-red"
                      : row.drift > 0.15
                      ? "text-terminal-amber"
                      : "text-terminal-green"
                  }
                >
                  {row.drift.toFixed(2)}
                </span>
              ),
            },
            {
              key: "reliability",
              header: "Reliability",
              render: (row) => (
                <span
                  className={
                    row.reliability < 0.5
                      ? "text-terminal-red"
                      : row.reliability < 0.8
                      ? "text-terminal-amber"
                      : "text-terminal-green"
                  }
                >
                  {row.reliability.toFixed(2)}
                </span>
              ),
            },
            {
              key: "template",
              header: "Template",
              render: (row) => row.template || "-",
            },
            { key: "extractor", header: "Extractor" },
            { key: "timestamp", header: "Timestamp" },
          ]}
          data={filteredEvaluations}
          onRowClick={(row) => {
            // TODO: Navigate to evaluation detail
            console.log("View evaluation:", row.id);
          }}
          emptyMessage="No evaluations match your filters"
        />
      </Box>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-terminal-white-dim">
          Showing {filteredEvaluations.length} of {mockEvaluations.length}{" "}
          evaluations
        </span>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" disabled>
            [&lt;] Previous
          </Button>
          <span className="px-4 py-2 text-terminal-white-dim">Page 1 of 1</span>
          <Button variant="secondary" size="sm" disabled>
            [&gt;] Next
          </Button>
        </div>
      </div>
    </div>
  );
}
