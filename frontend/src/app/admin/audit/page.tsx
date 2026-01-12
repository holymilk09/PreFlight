"use client";

import { useState } from "react";
import { Box, Input, Table } from "@/components/ui";

// Mock data
const mockAuditLogs = [
  {
    id: "audit-001",
    timestamp: "2024-01-15 14:32:15",
    tenant: "Acme Corp",
    actor: "admin@acmecorp.com",
    action: "API_KEY_CREATE",
    resource: "api_key:cp_a3f8...",
    details: "Created production API key",
    ip: "192.168.1.100",
  },
  {
    id: "audit-002",
    timestamp: "2024-01-15 14:28:45",
    tenant: "TechStart Inc",
    actor: "ops@techstart.io",
    action: "TEMPLATE_UPDATE",
    resource: "template:INV-TECH-001",
    details: "Updated baseline_reliability to 0.85",
    ip: "10.0.0.45",
  },
  {
    id: "audit-003",
    timestamp: "2024-01-15 14:22:12",
    tenant: "DocuFlow AI",
    actor: "dev@docuflow.ai",
    action: "EVALUATION",
    resource: "eval:eval-8834",
    details: "Evaluation completed: MATCH",
    ip: "172.16.0.22",
  },
  {
    id: "audit-004",
    timestamp: "2024-01-15 14:18:33",
    tenant: "FastDocs LLC",
    actor: "team@fastdocs.com",
    action: "API_KEY_ROTATE",
    resource: "api_key:cp_x9d4...",
    details: "Rotated API key",
    ip: "192.168.2.50",
  },
  {
    id: "audit-005",
    timestamp: "2024-01-15 14:12:08",
    tenant: "ExtractCo",
    actor: "SYSTEM",
    action: "RATE_LIMIT",
    resource: "tenant:extractco",
    details: "Rate limit enforced: 1000 req/min exceeded",
    ip: "N/A",
  },
  {
    id: "audit-006",
    timestamp: "2024-01-15 14:05:22",
    tenant: "NewStartup",
    actor: "hello@newstartup.dev",
    action: "USER_LOGIN",
    resource: "user:hello@newstartup.dev",
    details: "Successful login",
    ip: "203.0.113.45",
  },
  {
    id: "audit-007",
    timestamp: "2024-01-15 13:58:15",
    tenant: "Acme Corp",
    actor: "admin@acmecorp.com",
    action: "TEMPLATE_CREATE",
    resource: "template:INV-ACME-002",
    details: "Created new template",
    ip: "192.168.1.100",
  },
  {
    id: "audit-008",
    timestamp: "2024-01-15 13:45:30",
    tenant: "SYSTEM",
    actor: "SYSTEM",
    action: "BACKUP_COMPLETE",
    resource: "database:primary",
    details: "Daily backup completed successfully",
    ip: "N/A",
  },
];

type ActionFilter =
  | "ALL"
  | "API_KEY"
  | "TEMPLATE"
  | "EVALUATION"
  | "USER"
  | "SYSTEM";

export default function AuditPage() {
  const [search, setSearch] = useState("");
  const [actionFilter, setActionFilter] = useState<ActionFilter>("ALL");

  const filteredLogs = mockAuditLogs.filter((log) => {
    const matchesSearch =
      search === "" ||
      log.tenant.toLowerCase().includes(search.toLowerCase()) ||
      log.actor.toLowerCase().includes(search.toLowerCase()) ||
      log.details.toLowerCase().includes(search.toLowerCase());

    let matchesAction = actionFilter === "ALL";
    if (actionFilter === "API_KEY") {
      matchesAction = log.action.startsWith("API_KEY");
    } else if (actionFilter === "TEMPLATE") {
      matchesAction = log.action.startsWith("TEMPLATE");
    } else if (actionFilter === "EVALUATION") {
      matchesAction = log.action === "EVALUATION";
    } else if (actionFilter === "USER") {
      matchesAction = log.action.startsWith("USER");
    } else if (actionFilter === "SYSTEM") {
      matchesAction =
        log.action === "RATE_LIMIT" || log.action.includes("BACKUP");
    }

    return matchesSearch && matchesAction;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl text-terminal-white">Audit Log</h1>
          <p className="text-terminal-white-dim text-sm">
            System-wide activity and compliance log
          </p>
        </div>
        <div className="text-terminal-white-dim text-sm">
          {mockAuditLogs.length} total entries
        </div>
      </div>

      {/* Filters */}
      <Box title="FILTERS">
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <Input
              placeholder="Search by tenant, actor, or details..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            {(
              [
                "ALL",
                "API_KEY",
                "TEMPLATE",
                "EVALUATION",
                "USER",
                "SYSTEM",
              ] as ActionFilter[]
            ).map((action) => (
              <button
                key={action}
                onClick={() => setActionFilter(action)}
                className={`px-3 py-2 text-sm transition-colors ${
                  actionFilter === action
                    ? "bg-terminal-green text-terminal-black"
                    : "text-terminal-white-dim hover:text-terminal-green border border-terminal-gray"
                }`}
              >
                {action.replace("_", " ")}
              </button>
            ))}
          </div>
        </div>
      </Box>

      {/* Audit Log */}
      <Box title={`AUDIT LOG (${filteredLogs.length})`}>
        <Table
          columns={[
            { key: "timestamp", header: "Timestamp", width: "w-40" },
            { key: "tenant", header: "Tenant" },
            { key: "actor", header: "Actor" },
            {
              key: "action",
              header: "Action",
              render: (row) => (
                <span
                  className={
                    row.action.includes("CREATE")
                      ? "text-terminal-green"
                      : row.action.includes("DELETE") ||
                        row.action.includes("REVOKE")
                      ? "text-terminal-red"
                      : row.action.includes("UPDATE") ||
                        row.action.includes("ROTATE")
                      ? "text-terminal-amber"
                      : "text-terminal-cyan"
                  }
                >
                  [{row.action}]
                </span>
              ),
            },
            { key: "details", header: "Details" },
            {
              key: "ip",
              header: "IP",
              render: (row) => (
                <span className="text-terminal-white-dim">{row.ip}</span>
              ),
            },
          ]}
          data={filteredLogs}
          emptyMessage="No audit logs match your filters"
        />
      </Box>

      {/* Info */}
      <Box title="COMPLIANCE INFO">
        <div className="text-terminal-white-dim text-sm space-y-2">
          <p>
            All audit logs are retained for 90 days (Team plan) or 365 days
            (Enterprise plan).
          </p>
          <p>
            Logs include: API key operations, template changes, evaluation
            requests, authentication events, and system operations.
          </p>
          <p>Export functionality is available for Enterprise customers.</p>
        </div>
      </Box>
    </div>
  );
}
