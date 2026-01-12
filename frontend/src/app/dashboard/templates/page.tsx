"use client";

import { useState } from "react";
import { Box, Button, Input, Modal, StatusBadge, Table, Progress } from "@/components/ui";

// Mock data
const mockTemplates = [
  {
    id: "INV-ACME-001",
    name: "ACME Corporation Invoices",
    status: "ACTIVE" as const,
    evaluations: 4521,
    avgDrift: 0.08,
    avgReliability: 0.94,
    baselineReliability: 0.90,
    created: "2024-01-01",
    lastEval: "2 min ago",
  },
  {
    id: "RCP-VENDOR-02",
    name: "Vendor Receipts",
    status: "ACTIVE" as const,
    evaluations: 2134,
    avgDrift: 0.15,
    avgReliability: 0.87,
    baselineReliability: 0.85,
    created: "2024-01-05",
    lastEval: "5 min ago",
  },
  {
    id: "CON-LEGAL-01",
    name: "Legal Contracts",
    status: "REVIEW" as const,
    evaluations: 892,
    avgDrift: 0.31,
    avgReliability: 0.72,
    baselineReliability: 0.80,
    created: "2024-01-10",
    lastEval: "1 hour ago",
  },
  {
    id: "PO-SUPPLY-03",
    name: "Supply Chain POs",
    status: "ACTIVE" as const,
    evaluations: 1567,
    avgDrift: 0.11,
    avgReliability: 0.91,
    baselineReliability: 0.88,
    created: "2024-01-08",
    lastEval: "15 min ago",
  },
  {
    id: "INV-OLD-001",
    name: "Legacy Invoice Format",
    status: "DEPRECATED" as const,
    evaluations: 8234,
    avgDrift: 0.45,
    avgReliability: 0.65,
    baselineReliability: 0.75,
    created: "2023-06-15",
    lastEval: "3 days ago",
  },
];

type TemplateStatus = "ALL" | "ACTIVE" | "REVIEW" | "DEPRECATED";

export default function TemplatesPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<TemplateStatus>("ALL");
  const [showCreateModal, setShowCreateModal] = useState(false);

  const filteredTemplates = mockTemplates.filter((t) => {
    const matchesSearch =
      search === "" ||
      t.id.toLowerCase().includes(search.toLowerCase()) ||
      t.name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus =
      statusFilter === "ALL" || t.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl text-terminal-white">Templates</h1>
          <p className="text-terminal-white-dim text-sm">
            Manage document templates and baselines
          </p>
        </div>
        <Button variant="primary" onClick={() => setShowCreateModal(true)}>
          [+] Create Template
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Box>
          <div className="text-terminal-white-dim text-sm">Total Templates</div>
          <div className="text-2xl text-terminal-green">
            {mockTemplates.length}
          </div>
        </Box>
        <Box>
          <div className="text-terminal-white-dim text-sm">Active</div>
          <div className="text-2xl text-terminal-green">
            {mockTemplates.filter((t) => t.status === "ACTIVE").length}
          </div>
        </Box>
        <Box>
          <div className="text-terminal-white-dim text-sm">Needs Review</div>
          <div className="text-2xl text-terminal-amber">
            {mockTemplates.filter((t) => t.status === "REVIEW").length}
          </div>
        </Box>
        <Box>
          <div className="text-terminal-white-dim text-sm">
            Total Evaluations
          </div>
          <div className="text-2xl text-terminal-green">
            {mockTemplates
              .reduce((sum, t) => sum + t.evaluations, 0)
              .toLocaleString()}
          </div>
        </Box>
      </div>

      {/* Filters */}
      <Box title="FILTERS">
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <Input
              placeholder="Search by ID or name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            {(["ALL", "ACTIVE", "REVIEW", "DEPRECATED"] as TemplateStatus[]).map(
              (status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`px-3 py-2 text-sm transition-colors ${
                    statusFilter === status
                      ? "bg-terminal-green text-terminal-black"
                      : "text-terminal-white-dim hover:text-terminal-green border border-terminal-gray"
                  }`}
                >
                  {status}
                </button>
              )
            )}
          </div>
        </div>
      </Box>

      {/* Templates List */}
      <Box title={`TEMPLATES (${filteredTemplates.length})`}>
        <Table
          columns={[
            { key: "id", header: "Template ID", width: "w-36" },
            { key: "name", header: "Name" },
            {
              key: "status",
              header: "Status",
              render: (row) => (
                <StatusBadge
                  status={
                    row.status === "DEPRECATED"
                      ? "REJECT"
                      : row.status
                  }
                />
              ),
            },
            {
              key: "evaluations",
              header: "Evaluations",
              render: (row) => row.evaluations.toLocaleString(),
            },
            {
              key: "avgDrift",
              header: "Avg Drift",
              render: (row) => (
                <span
                  className={
                    row.avgDrift > 0.3
                      ? "text-terminal-red"
                      : row.avgDrift > 0.15
                      ? "text-terminal-amber"
                      : "text-terminal-green"
                  }
                >
                  {row.avgDrift.toFixed(2)}
                </span>
              ),
            },
            {
              key: "avgReliability",
              header: "Reliability",
              render: (row) => (
                <Progress
                  value={row.avgReliability * 100}
                  width={10}
                  showPercent={false}
                  variant={
                    row.avgReliability < 0.7
                      ? "error"
                      : row.avgReliability < 0.85
                      ? "warning"
                      : "success"
                  }
                />
              ),
            },
            { key: "lastEval", header: "Last Eval" },
          ]}
          data={filteredTemplates}
          onRowClick={(row) => {
            // TODO: Navigate to template detail
            console.log("View template:", row.id);
          }}
          emptyMessage="No templates match your filters"
        />
      </Box>

      {/* Create Template Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="CREATE TEMPLATE"
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => setShowCreateModal(false)}
            >
              Cancel
            </Button>
            <Button variant="primary">Create Template</Button>
          </div>
        }
      >
        <div className="space-y-4">
          <Input label="Template ID" placeholder="e.g., INV-VENDOR-001" />
          <Input label="Name" placeholder="e.g., Vendor Invoices" />
          <Input
            label="Baseline Reliability"
            type="number"
            placeholder="0.85"
            hint="Target reliability threshold (0.0 - 1.0)"
          />
          <div className="text-terminal-white-dim text-sm">
            <p>
              Templates are created automatically when you process documents
              that don&apos;t match existing templates.
            </p>
            <p className="mt-2">
              Use manual creation only when you need to pre-define baselines.
            </p>
          </div>
        </div>
      </Modal>
    </div>
  );
}
