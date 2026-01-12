"use client";

import { useState } from "react";
import { Box, Button, Input, Table } from "@/components/ui";

// Mock data
const mockErrors = [
  {
    id: "err-001",
    timestamp: "2024-01-15 14:32:15",
    tenant: "FastDocs LLC",
    type: "RATE_LIMIT",
    message: "Rate limit exceeded: 1000 requests/min",
    endpoint: "POST /v1/evaluate",
    statusCode: 429,
    resolved: false,
  },
  {
    id: "err-002",
    timestamp: "2024-01-15 14:28:45",
    tenant: "NewClient Corp",
    type: "AUTH_FAILED",
    message: "Invalid API key: cp_x8f9...",
    endpoint: "POST /v1/evaluate",
    statusCode: 401,
    resolved: false,
  },
  {
    id: "err-003",
    timestamp: "2024-01-15 14:22:12",
    tenant: "TechStart Inc",
    type: "TIMEOUT",
    message: "Database query timeout after 3000ms",
    endpoint: "POST /v1/evaluate",
    statusCode: 504,
    resolved: true,
  },
  {
    id: "err-004",
    timestamp: "2024-01-15 14:18:33",
    tenant: "ExtractCo",
    type: "VALIDATION",
    message: "Invalid feature vector: expected 128 dimensions, got 64",
    endpoint: "POST /v1/evaluate",
    statusCode: 400,
    resolved: true,
  },
  {
    id: "err-005",
    timestamp: "2024-01-15 14:12:08",
    tenant: "DocuFlow AI",
    type: "INTERNAL",
    message: "NullPointerException in TemplateMatcher.match()",
    endpoint: "POST /v1/evaluate",
    statusCode: 500,
    resolved: true,
  },
  {
    id: "err-006",
    timestamp: "2024-01-15 14:05:22",
    tenant: "Acme Corp",
    type: "RATE_LIMIT",
    message: "Rate limit exceeded: 1000 requests/min",
    endpoint: "POST /v1/evaluate",
    statusCode: 429,
    resolved: true,
  },
];

type ErrorType = "ALL" | "RATE_LIMIT" | "AUTH_FAILED" | "TIMEOUT" | "VALIDATION" | "INTERNAL";

export default function ErrorsPage() {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<ErrorType>("ALL");
  const [showResolved, setShowResolved] = useState(true);

  const filteredErrors = mockErrors.filter((e) => {
    const matchesSearch =
      search === "" ||
      e.tenant.toLowerCase().includes(search.toLowerCase()) ||
      e.message.toLowerCase().includes(search.toLowerCase());
    const matchesType = typeFilter === "ALL" || e.type === typeFilter;
    const matchesResolved = showResolved || !e.resolved;
    return matchesSearch && matchesType && matchesResolved;
  });

  const errorCounts = {
    total: mockErrors.length,
    unresolved: mockErrors.filter((e) => !e.resolved).length,
    today: mockErrors.filter((e) =>
      e.timestamp.startsWith("2024-01-15")
    ).length,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl text-terminal-white">Error Log</h1>
          <p className="text-terminal-white-dim text-sm">
            System errors and exceptions
          </p>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-terminal-amber text-sm">
            {errorCounts.unresolved} unresolved
          </span>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Box>
          <div className="text-terminal-white-dim text-sm">Total Errors</div>
          <div className="text-2xl text-terminal-red">{errorCounts.total}</div>
        </Box>
        <Box>
          <div className="text-terminal-white-dim text-sm">Unresolved</div>
          <div className="text-2xl text-terminal-amber">
            {errorCounts.unresolved}
          </div>
        </Box>
        <Box>
          <div className="text-terminal-white-dim text-sm">Today</div>
          <div className="text-2xl text-terminal-white">
            {errorCounts.today}
          </div>
        </Box>
        <Box>
          <div className="text-terminal-white-dim text-sm">Error Rate</div>
          <div className="text-2xl text-terminal-green">0.02%</div>
        </Box>
      </div>

      {/* Filters */}
      <Box title="FILTERS">
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <Input
              placeholder="Search by tenant or message..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            {(
              [
                "ALL",
                "RATE_LIMIT",
                "AUTH_FAILED",
                "TIMEOUT",
                "VALIDATION",
                "INTERNAL",
              ] as ErrorType[]
            ).map((type) => (
              <button
                key={type}
                onClick={() => setTypeFilter(type)}
                className={`px-3 py-2 text-sm transition-colors ${
                  typeFilter === type
                    ? "bg-terminal-red text-terminal-black"
                    : "text-terminal-white-dim hover:text-terminal-red border border-terminal-gray"
                }`}
              >
                {type === "ALL" ? "ALL" : type.replace("_", " ")}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-terminal-white-dim text-sm">
            <input
              type="checkbox"
              checked={showResolved}
              onChange={(e) => setShowResolved(e.target.checked)}
              className="bg-terminal-darkgray border border-terminal-gray"
            />
            Show resolved
          </label>
        </div>
      </Box>

      {/* Errors List */}
      <Box title={`ERRORS (${filteredErrors.length})`} variant="error">
        <Table
          columns={[
            { key: "timestamp", header: "Timestamp", width: "w-40" },
            { key: "tenant", header: "Tenant" },
            {
              key: "type",
              header: "Type",
              render: (row) => (
                <span className="text-terminal-red">[{row.type}]</span>
              ),
            },
            { key: "message", header: "Message" },
            {
              key: "statusCode",
              header: "Status",
              render: (row) => (
                <span
                  className={
                    row.statusCode >= 500
                      ? "text-terminal-red"
                      : row.statusCode >= 400
                      ? "text-terminal-amber"
                      : "text-terminal-green"
                  }
                >
                  {row.statusCode}
                </span>
              ),
            },
            {
              key: "resolved",
              header: "State",
              render: (row) => (
                <span
                  className={
                    row.resolved ? "text-terminal-green" : "text-terminal-amber"
                  }
                >
                  {row.resolved ? "[RESOLVED]" : "[OPEN]"}
                </span>
              ),
            },
            {
              key: "actions",
              header: "",
              render: (row) =>
                !row.resolved && (
                  <Button variant="ghost" size="sm">
                    Resolve
                  </Button>
                ),
            },
          ]}
          data={filteredErrors}
          emptyMessage="No errors match your filters"
        />
      </Box>
    </div>
  );
}
