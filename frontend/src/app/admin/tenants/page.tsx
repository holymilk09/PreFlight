"use client";

import { useState } from "react";
import { Box, Button, Input, Table } from "@/components/ui";

// Mock data
const mockTenants = [
  {
    id: "tenant-1",
    name: "Acme Corp",
    email: "admin@acmecorp.com",
    plan: "Enterprise",
    evaluations: 67234,
    templates: 45,
    apiKeys: 3,
    avgDrift: 0.08,
    status: "active",
    created: "2023-06-15",
  },
  {
    id: "tenant-2",
    name: "TechStart Inc",
    email: "ops@techstart.io",
    plan: "Team",
    evaluations: 45123,
    templates: 28,
    apiKeys: 2,
    avgDrift: 0.12,
    status: "active",
    created: "2023-09-20",
  },
  {
    id: "tenant-3",
    name: "DocuFlow AI",
    email: "support@docuflow.ai",
    plan: "Developer",
    evaluations: 28456,
    templates: 15,
    apiKeys: 2,
    avgDrift: 0.15,
    status: "active",
    created: "2023-11-01",
  },
  {
    id: "tenant-4",
    name: "FastDocs LLC",
    email: "team@fastdocs.com",
    plan: "Developer",
    evaluations: 24567,
    templates: 12,
    apiKeys: 1,
    avgDrift: 0.31,
    status: "warning",
    created: "2023-12-10",
  },
  {
    id: "tenant-5",
    name: "ExtractCo",
    email: "dev@extractco.io",
    plan: "Team",
    evaluations: 21345,
    templates: 18,
    apiKeys: 2,
    avgDrift: 0.09,
    status: "active",
    created: "2024-01-05",
  },
  {
    id: "tenant-6",
    name: "NewStartup",
    email: "hello@newstartup.dev",
    plan: "Free",
    evaluations: 856,
    templates: 3,
    apiKeys: 1,
    avgDrift: 0.22,
    status: "active",
    created: "2024-01-12",
  },
];

type PlanFilter = "ALL" | "Free" | "Developer" | "Team" | "Enterprise";

export default function TenantsPage() {
  const [search, setSearch] = useState("");
  const [planFilter, setPlanFilter] = useState<PlanFilter>("ALL");

  const filteredTenants = mockTenants.filter((t) => {
    const matchesSearch =
      search === "" ||
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.email.toLowerCase().includes(search.toLowerCase());
    const matchesPlan = planFilter === "ALL" || t.plan === planFilter;
    return matchesSearch && matchesPlan;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl text-terminal-white">Tenants</h1>
          <p className="text-terminal-white-dim text-sm">
            Manage all tenant accounts
          </p>
        </div>
        <div className="text-terminal-white-dim text-sm">
          Total: {mockTenants.length} tenants
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Box>
          <div className="text-terminal-white-dim text-sm">Total Tenants</div>
          <div className="text-2xl text-terminal-green">{mockTenants.length}</div>
        </Box>
        <Box>
          <div className="text-terminal-white-dim text-sm">Active Today</div>
          <div className="text-2xl text-terminal-green">
            {mockTenants.filter((t) => t.status === "active").length}
          </div>
        </Box>
        <Box>
          <div className="text-terminal-white-dim text-sm">Needs Attention</div>
          <div className="text-2xl text-terminal-amber">
            {mockTenants.filter((t) => t.status === "warning").length}
          </div>
        </Box>
        <Box>
          <div className="text-terminal-white-dim text-sm">
            Total Evaluations
          </div>
          <div className="text-2xl text-terminal-green">
            {mockTenants
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
              placeholder="Search by name or email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            {(
              ["ALL", "Free", "Developer", "Team", "Enterprise"] as PlanFilter[]
            ).map((plan) => (
              <button
                key={plan}
                onClick={() => setPlanFilter(plan)}
                className={`px-3 py-2 text-sm transition-colors ${
                  planFilter === plan
                    ? "bg-terminal-green text-terminal-black"
                    : "text-terminal-white-dim hover:text-terminal-green border border-terminal-gray"
                }`}
              >
                {plan}
              </button>
            ))}
          </div>
        </div>
      </Box>

      {/* Tenants List */}
      <Box title={`TENANTS (${filteredTenants.length})`}>
        <Table
          columns={[
            { key: "name", header: "Tenant Name" },
            { key: "email", header: "Email" },
            {
              key: "plan",
              header: "Plan",
              render: (row) => (
                <span
                  className={
                    row.plan === "Enterprise"
                      ? "text-terminal-amber"
                      : row.plan === "Team"
                      ? "text-terminal-cyan"
                      : "text-terminal-white-dim"
                  }
                >
                  {row.plan}
                </span>
              ),
            },
            {
              key: "evaluations",
              header: "Evaluations",
              render: (row) => row.evaluations.toLocaleString(),
            },
            { key: "templates", header: "Templates" },
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
              key: "status",
              header: "Status",
              render: (row) => (
                <span
                  className={
                    row.status === "active"
                      ? "text-terminal-green"
                      : "text-terminal-amber"
                  }
                >
                  [{row.status.toUpperCase()}]
                </span>
              ),
            },
            {
              key: "actions",
              header: "Actions",
              render: () => (
                <Button variant="ghost" size="sm">
                  View
                </Button>
              ),
            },
          ]}
          data={filteredTenants}
          emptyMessage="No tenants match your filters"
        />
      </Box>
    </div>
  );
}
