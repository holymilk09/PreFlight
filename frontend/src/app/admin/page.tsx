"use client";

import { Box, Progress, Sparkline, Table } from "@/components/ui";

// Mock data
const mockSystemStats = {
  totalTenants: 47,
  activeTenants: 42,
  evaluationsToday: 52847,
  evaluationsWeek: 287432,
  errorRate: 0.02,
  avgLatency: 45,
  p95Latency: 145,
  p99Latency: 287,
};

const mockTopTenants = [
  {
    id: "tenant-1",
    name: "Acme Corp",
    evalsToday: 12847,
    evalsWeek: 67234,
    avgDrift: 0.08,
    status: "healthy",
  },
  {
    id: "tenant-2",
    name: "TechStart Inc",
    evalsToday: 8234,
    evalsWeek: 45123,
    avgDrift: 0.12,
    status: "healthy",
  },
  {
    id: "tenant-3",
    name: "DocuFlow AI",
    evalsToday: 5102,
    evalsWeek: 28456,
    avgDrift: 0.15,
    status: "healthy",
  },
  {
    id: "tenant-4",
    name: "FastDocs LLC",
    evalsToday: 4521,
    evalsWeek: 24567,
    avgDrift: 0.31,
    status: "warning",
  },
  {
    id: "tenant-5",
    name: "ExtractCo",
    evalsToday: 3890,
    evalsWeek: 21345,
    avgDrift: 0.09,
    status: "healthy",
  },
];

const mockRecentErrors = [
  {
    id: "err-1",
    tenant: "FastDocs LLC",
    type: "RATE_LIMIT",
    message: "Rate limit exceeded (1000/min)",
    time: "2 min ago",
  },
  {
    id: "err-2",
    tenant: "NewClient Corp",
    type: "AUTH_FAILED",
    message: "Invalid API key",
    time: "5 min ago",
  },
  {
    id: "err-3",
    tenant: "TechStart Inc",
    type: "TIMEOUT",
    message: "Database query timeout (3s)",
    time: "12 min ago",
  },
  {
    id: "err-4",
    tenant: "ExtractCo",
    type: "VALIDATION",
    message: "Invalid feature vector dimensions",
    time: "18 min ago",
  },
];

const latencyTrend = [42, 45, 48, 43, 41, 44, 46, 45, 43, 47, 44, 45];
const evalsTrend = [45000, 47000, 51000, 49000, 52000, 48000, 50000, 52000, 54000, 51000, 53000, 52847];

function StatCard({
  label,
  value,
  subValue,
  trend,
  status,
}: {
  label: string;
  value: string | number;
  subValue?: string;
  trend?: number[];
  status?: "good" | "warning" | "error";
}) {
  const statusColor =
    status === "error"
      ? "text-terminal-red"
      : status === "warning"
      ? "text-terminal-amber"
      : "text-terminal-green";

  return (
    <Box>
      <div className="text-terminal-white-dim text-sm mb-1">{label}</div>
      <div className={`text-2xl ${statusColor} mb-1`}>{value}</div>
      {subValue && (
        <div className="text-terminal-white-dim text-xs">{subValue}</div>
      )}
      {trend && (
        <div className="mt-2">
          <Sparkline data={trend} />
        </div>
      )}
    </Box>
  );
}

function SystemHealth() {
  const services = [
    { name: "API Gateway", status: "healthy", latency: "12ms" },
    { name: "PostgreSQL", status: "healthy", latency: "3ms" },
    { name: "Redis Cache", status: "healthy", latency: "1ms" },
    { name: "Temporal", status: "healthy", latency: "8ms" },
  ];

  return (
    <Box title="SYSTEM HEALTH">
      <div className="space-y-2">
        {services.map((s) => (
          <div key={s.name} className="flex items-center justify-between">
            <span className="text-terminal-white-dim">{s.name}</span>
            <div className="flex items-center gap-4">
              <span className="text-terminal-white-dim text-sm">
                {s.latency}
              </span>
              <span
                className={`${
                  s.status === "healthy"
                    ? "text-terminal-green"
                    : "text-terminal-red"
                }`}
              >
                {s.status === "healthy" ? "[OK]" : "[FAIL]"}
              </span>
            </div>
          </div>
        ))}
      </div>
    </Box>
  );
}

export default function AdminPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl text-terminal-white">System Overview</h1>
          <p className="text-terminal-white-dim text-sm">
            Real-time monitoring of all tenants and infrastructure
          </p>
        </div>
        <div className="text-terminal-green text-sm">
          All systems operational
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="TOTAL TENANTS"
          value={mockSystemStats.totalTenants}
          subValue={`${mockSystemStats.activeTenants} active today`}
        />
        <StatCard
          label="EVALUATIONS TODAY"
          value={mockSystemStats.evaluationsToday.toLocaleString()}
          subValue={`${mockSystemStats.evaluationsWeek.toLocaleString()} this week`}
          trend={evalsTrend}
        />
        <StatCard
          label="ERROR RATE"
          value={`${mockSystemStats.errorRate}%`}
          status={mockSystemStats.errorRate > 1 ? "error" : "good"}
        />
        <StatCard
          label="AVG LATENCY"
          value={`${mockSystemStats.avgLatency}ms`}
          subValue={`P95: ${mockSystemStats.p95Latency}ms | P99: ${mockSystemStats.p99Latency}ms`}
          trend={latencyTrend}
          status={mockSystemStats.avgLatency > 100 ? "warning" : "good"}
        />
      </div>

      {/* Health and Top Tenants Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <SystemHealth />
        <div className="lg:col-span-2">
          <Box title="TOP TENANTS (BY USAGE TODAY)">
            <Table
              columns={[
                { key: "name", header: "Tenant" },
                {
                  key: "evalsToday",
                  header: "Today",
                  render: (row) => row.evalsToday.toLocaleString(),
                },
                {
                  key: "evalsWeek",
                  header: "This Week",
                  render: (row) => row.evalsWeek.toLocaleString(),
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
                  key: "status",
                  header: "Status",
                  render: (row) => (
                    <span
                      className={
                        row.status === "healthy"
                          ? "text-terminal-green"
                          : "text-terminal-amber"
                      }
                    >
                      [{row.status.toUpperCase()}]
                    </span>
                  ),
                },
              ]}
              data={mockTopTenants}
              onRowClick={(row) => {
                console.log("View tenant:", row.id);
              }}
            />
          </Box>
        </div>
      </div>

      {/* Errors and Usage */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Box title="RECENT ERRORS" variant="error">
          <Table
            columns={[
              { key: "tenant", header: "Tenant" },
              {
                key: "type",
                header: "Type",
                render: (row) => (
                  <span className="text-terminal-red">[{row.type}]</span>
                ),
              },
              { key: "message", header: "Message" },
              { key: "time", header: "Time" },
            ]}
            data={mockRecentErrors}
            emptyMessage="No recent errors"
          />
        </Box>

        <Box title="USAGE DISTRIBUTION">
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-terminal-white-dim">Free Tier</span>
                <span className="text-terminal-white-dim">18 tenants</span>
              </div>
              <Progress value={38} showPercent={false} />
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-terminal-white-dim">Developer</span>
                <span className="text-terminal-white-dim">21 tenants</span>
              </div>
              <Progress value={45} showPercent={false} />
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-terminal-white-dim">Team</span>
                <span className="text-terminal-white-dim">6 tenants</span>
              </div>
              <Progress value={13} showPercent={false} />
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-terminal-white-dim">Enterprise</span>
                <span className="text-terminal-white-dim">2 tenants</span>
              </div>
              <Progress value={4} showPercent={false} />
            </div>
          </div>
        </Box>
      </div>

      {/* Quick Links */}
      <Box title="ADMIN ACTIONS">
        <div className="flex flex-wrap gap-4">
          <a
            href="/admin/tenants"
            className="text-terminal-green hover:underline"
          >
            [T] View All Tenants
          </a>
          <a
            href="/admin/health"
            className="text-terminal-green hover:underline"
          >
            [H] System Health Details
          </a>
          <a
            href="/admin/errors"
            className="text-terminal-green hover:underline"
          >
            [!] Error Log
          </a>
          <a
            href="/admin/audit"
            className="text-terminal-green hover:underline"
          >
            [A] Audit Log
          </a>
        </div>
      </Box>
    </div>
  );
}
