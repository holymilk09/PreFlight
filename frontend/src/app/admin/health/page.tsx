"use client";

import { Box, Sparkline, Table } from "@/components/ui";

// Mock data
const mockServices = [
  {
    name: "API Gateway",
    status: "healthy",
    uptime: 99.99,
    latency: 12,
    p95: 45,
    p99: 89,
    requests: 52847,
    errors: 3,
  },
  {
    name: "PostgreSQL Primary",
    status: "healthy",
    uptime: 99.98,
    latency: 3,
    p95: 8,
    p99: 15,
    requests: 128456,
    errors: 0,
  },
  {
    name: "PostgreSQL Replica",
    status: "healthy",
    uptime: 99.97,
    latency: 4,
    p95: 9,
    p99: 18,
    requests: 45123,
    errors: 0,
  },
  {
    name: "Redis Cache",
    status: "healthy",
    uptime: 100,
    latency: 1,
    p95: 2,
    p99: 5,
    requests: 287456,
    errors: 0,
  },
  {
    name: "Temporal Server",
    status: "healthy",
    uptime: 99.95,
    latency: 8,
    p95: 25,
    p99: 45,
    requests: 12847,
    errors: 2,
  },
];

const latencyHistory = {
  api: [12, 14, 11, 13, 15, 12, 11, 14, 12, 13, 11, 12],
  db: [3, 4, 3, 3, 5, 3, 4, 3, 3, 4, 3, 3],
  redis: [1, 1, 1, 2, 1, 1, 1, 1, 2, 1, 1, 1],
};

const mockAlerts = [
  {
    id: "alert-1",
    service: "API Gateway",
    type: "WARNING",
    message: "High latency spike detected (145ms)",
    time: "15 min ago",
    resolved: true,
  },
  {
    id: "alert-2",
    service: "PostgreSQL Primary",
    type: "INFO",
    message: "Routine backup completed",
    time: "1 hour ago",
    resolved: true,
  },
  {
    id: "alert-3",
    service: "Temporal Server",
    type: "WARNING",
    message: "Workflow queue depth increased",
    time: "2 hours ago",
    resolved: true,
  },
];

function StatusIndicator({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center gap-2 ${
        status === "healthy"
          ? "text-terminal-green"
          : status === "degraded"
          ? "text-terminal-amber"
          : "text-terminal-red"
      }`}
    >
      <span className="inline-block w-2 h-2 rounded-full bg-current animate-pulse" />
      {status.toUpperCase()}
    </span>
  );
}

export default function HealthPage() {
  const allHealthy = mockServices.every((s) => s.status === "healthy");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl text-terminal-white">System Health</h1>
          <p className="text-terminal-white-dim text-sm">
            Infrastructure monitoring and metrics
          </p>
        </div>
        <div
          className={`text-sm ${
            allHealthy ? "text-terminal-green" : "text-terminal-amber"
          }`}
        >
          {allHealthy
            ? "All systems operational"
            : "Some systems need attention"}
        </div>
      </div>

      {/* Overall Status */}
      <Box
        title="SYSTEM STATUS"
        variant={allHealthy ? "highlight" : "warning"}
      >
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          <div>
            <div className="text-3xl text-terminal-green mb-1">
              {mockServices.filter((s) => s.status === "healthy").length}/
              {mockServices.length}
            </div>
            <div className="text-terminal-white-dim text-sm">
              Services Healthy
            </div>
          </div>
          <div>
            <div className="text-3xl text-terminal-green mb-1">99.98%</div>
            <div className="text-terminal-white-dim text-sm">Avg Uptime</div>
          </div>
          <div>
            <div className="text-3xl text-terminal-green mb-1">45ms</div>
            <div className="text-terminal-white-dim text-sm">
              Avg Response Time
            </div>
          </div>
          <div>
            <div className="text-3xl text-terminal-green mb-1">0.01%</div>
            <div className="text-terminal-white-dim text-sm">Error Rate</div>
          </div>
        </div>
      </Box>

      {/* Services Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {mockServices.map((service) => (
          <Box key={service.name} title={service.name.toUpperCase()}>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-terminal-white-dim">Status</span>
                <StatusIndicator status={service.status} />
              </div>
              <div className="flex justify-between items-center">
                <span className="text-terminal-white-dim">Uptime</span>
                <span className="text-terminal-green">{service.uptime}%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-terminal-white-dim">Latency</span>
                <span className="text-terminal-green">{service.latency}ms</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-terminal-white-dim">P95/P99</span>
                <span className="text-terminal-white-dim">
                  {service.p95}ms / {service.p99}ms
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-terminal-white-dim">Requests</span>
                <span className="text-terminal-green">
                  {service.requests.toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-terminal-white-dim">Errors</span>
                <span
                  className={
                    service.errors > 0
                      ? "text-terminal-amber"
                      : "text-terminal-green"
                  }
                >
                  {service.errors}
                </span>
              </div>
            </div>
          </Box>
        ))}
      </div>

      {/* Latency Charts */}
      <Box title="LATENCY TRENDS (24H)">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <div className="text-terminal-white-dim text-sm mb-2">
              API Gateway
            </div>
            <Sparkline data={latencyHistory.api} />
            <div className="text-terminal-green text-sm mt-1">avg: 12ms</div>
          </div>
          <div>
            <div className="text-terminal-white-dim text-sm mb-2">Database</div>
            <Sparkline data={latencyHistory.db} />
            <div className="text-terminal-green text-sm mt-1">avg: 3ms</div>
          </div>
          <div>
            <div className="text-terminal-white-dim text-sm mb-2">Redis</div>
            <Sparkline data={latencyHistory.redis} />
            <div className="text-terminal-green text-sm mt-1">avg: 1ms</div>
          </div>
        </div>
      </Box>

      {/* Recent Alerts */}
      <Box title="RECENT ALERTS">
        <Table
          columns={[
            { key: "service", header: "Service" },
            {
              key: "type",
              header: "Type",
              render: (row) => (
                <span
                  className={
                    row.type === "WARNING"
                      ? "text-terminal-amber"
                      : row.type === "ERROR"
                      ? "text-terminal-red"
                      : "text-terminal-cyan"
                  }
                >
                  [{row.type}]
                </span>
              ),
            },
            { key: "message", header: "Message" },
            { key: "time", header: "Time" },
            {
              key: "resolved",
              header: "Status",
              render: (row) => (
                <span
                  className={
                    row.resolved ? "text-terminal-green" : "text-terminal-amber"
                  }
                >
                  {row.resolved ? "[RESOLVED]" : "[ACTIVE]"}
                </span>
              ),
            },
          ]}
          data={mockAlerts}
          emptyMessage="No recent alerts"
        />
      </Box>
    </div>
  );
}
