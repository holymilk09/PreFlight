"use client";

import { useState, ReactNode } from "react";

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

// Card component
function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`bg-white/[0.02] border border-white/5 rounded-2xl p-6 ${className}`}>
      {children}
    </div>
  );
}

// Stat card
function StatCard({ label, value, color = "text-white" }: { label: string; value: string | number; color?: string }) {
  return (
    <Card>
      <div className="text-sm text-white/40 mb-1">{label}</div>
      <div className={`text-2xl font-semibold ${color}`}>{value}</div>
    </Card>
  );
}

// Status badge
function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    ACTIVE: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    REVIEW: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    DEPRECATED: "bg-red-500/10 text-red-400 border-red-500/20",
  };

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium border ${styles[status] || styles.ACTIVE}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${
        status === "ACTIVE" ? "bg-emerald-400" : status === "REVIEW" ? "bg-amber-400" : "bg-red-400"
      }`} />
      {status}
    </span>
  );
}

// Progress bar
function ProgressBar({ value, variant = "default" }: { value: number; variant?: "success" | "warning" | "error" | "default" }) {
  const colors = {
    success: "bg-emerald-500",
    warning: "bg-amber-500",
    error: "bg-red-500",
    default: "bg-white/40",
  };

  return (
    <div className="w-20 h-1.5 bg-white/10 rounded-full overflow-hidden">
      <div
        className={`h-full ${colors[variant]} rounded-full transition-all`}
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

// Modal component
function Modal({
  isOpen,
  onClose,
  title,
  children,
}: {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-[#111] border border-white/10 rounded-2xl w-full max-w-md mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
          <h2 className="text-lg font-medium text-white">{title}</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-white/40 hover:text-white hover:bg-white/5 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  );
}

// Icons
const Icons = {
  plus: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4v16m8-8H4" />
    </svg>
  ),
  search: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  ),
};

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
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Templates</h1>
          <p className="text-white/40 mt-1">Manage document templates and baselines</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-black font-medium rounded-lg transition-colors"
        >
          {Icons.plus}
          <span>Create Template</span>
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Total Templates" value={mockTemplates.length} color="text-white" />
        <StatCard
          label="Active"
          value={mockTemplates.filter((t) => t.status === "ACTIVE").length}
          color="text-emerald-400"
        />
        <StatCard
          label="Needs Review"
          value={mockTemplates.filter((t) => t.status === "REVIEW").length}
          color="text-amber-400"
        />
        <StatCard
          label="Total Evaluations"
          value={mockTemplates.reduce((sum, t) => sum + t.evaluations, 0).toLocaleString()}
          color="text-white"
        />
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30">
            {Icons.search}
          </div>
          <input
            type="text"
            placeholder="Search by ID or name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-white/[0.02] border border-white/10 rounded-xl px-10 py-2.5 text-white placeholder-white/30 focus:outline-none focus:border-emerald-500/50 transition-colors"
          />
        </div>
        <div className="flex gap-2">
          {(["ALL", "ACTIVE", "REVIEW", "DEPRECATED"] as TemplateStatus[]).map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-4 py-2.5 text-sm font-medium rounded-xl transition-colors ${
                statusFilter === status
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  : "text-white/50 hover:text-white border border-white/10 hover:border-white/20"
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* Templates Table */}
      <Card className="overflow-hidden p-0">
        <div className="px-6 py-4 border-b border-white/5">
          <h3 className="text-lg font-medium text-white">
            Templates ({filteredTemplates.length})
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-xs text-white/30 border-b border-white/5">
                <th className="px-6 py-3 font-medium">Template ID</th>
                <th className="px-6 py-3 font-medium">Name</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium">Evaluations</th>
                <th className="px-6 py-3 font-medium">Avg Drift</th>
                <th className="px-6 py-3 font-medium">Reliability</th>
                <th className="px-6 py-3 font-medium">Last Eval</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              {filteredTemplates.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-white/30">
                    No templates match your filters
                  </td>
                </tr>
              ) : (
                filteredTemplates.map((template) => (
                  <tr
                    key={template.id}
                    className="border-b border-white/5 hover:bg-white/[0.02] cursor-pointer transition-colors"
                    onClick={() => console.log("View template:", template.id)}
                  >
                    <td className="px-6 py-4 text-white/80 font-mono text-xs">{template.id}</td>
                    <td className="px-6 py-4 text-white/70">{template.name}</td>
                    <td className="px-6 py-4">
                      <StatusBadge status={template.status} />
                    </td>
                    <td className="px-6 py-4 text-white/50">{template.evaluations.toLocaleString()}</td>
                    <td className={`px-6 py-4 ${
                      template.avgDrift > 0.3 ? "text-red-400" : template.avgDrift > 0.15 ? "text-amber-400" : "text-emerald-400"
                    }`}>
                      {template.avgDrift.toFixed(2)}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <ProgressBar
                          value={template.avgReliability * 100}
                          variant={
                            template.avgReliability < 0.7
                              ? "error"
                              : template.avgReliability < 0.85
                              ? "warning"
                              : "success"
                          }
                        />
                        <span className="text-white/40 text-xs">{(template.avgReliability * 100).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-white/30">{template.lastEval}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Create Template Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Create Template"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-white/60 mb-2">Template ID</label>
            <input
              type="text"
              placeholder="e.g., INV-VENDOR-001"
              className="w-full bg-white/[0.02] border border-white/10 rounded-xl px-4 py-2.5 text-white placeholder-white/30 focus:outline-none focus:border-emerald-500/50 transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm text-white/60 mb-2">Name</label>
            <input
              type="text"
              placeholder="e.g., Vendor Invoices"
              className="w-full bg-white/[0.02] border border-white/10 rounded-xl px-4 py-2.5 text-white placeholder-white/30 focus:outline-none focus:border-emerald-500/50 transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm text-white/60 mb-2">Baseline Reliability</label>
            <input
              type="number"
              placeholder="0.85"
              step="0.01"
              min="0"
              max="1"
              className="w-full bg-white/[0.02] border border-white/10 rounded-xl px-4 py-2.5 text-white placeholder-white/30 focus:outline-none focus:border-emerald-500/50 transition-colors"
            />
            <p className="text-xs text-white/30 mt-1">Target reliability threshold (0.0 - 1.0)</p>
          </div>
          <div className="bg-white/[0.02] border border-white/5 rounded-xl p-4 text-sm text-white/50">
            <p>Templates are created automatically when you process documents that don&apos;t match existing templates.</p>
            <p className="mt-2">Use manual creation only when you need to pre-define baselines.</p>
          </div>
          <div className="flex gap-3 pt-2">
            <button
              onClick={() => setShowCreateModal(false)}
              className="flex-1 px-4 py-2.5 border border-white/10 text-white/70 hover:bg-white/5 rounded-xl transition-colors"
            >
              Cancel
            </button>
            <button className="flex-1 px-4 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-black font-medium rounded-xl transition-colors">
              Create Template
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
