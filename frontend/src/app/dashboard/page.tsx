"use client";

import {
  Box,
  Progress,
  Sparkline,
  StatusBadge,
  Table,
  AnimatedCounter,
  TypewriterText,
  PulseGlow,
  ASCIIDocumentViz,
} from "@/components/ui";

// Mock data - will be replaced with API calls
const mockStats = {
  evaluationsToday: 1247,
  evaluationsWeek: 8934,
  matchRate: 78,
  avgDrift: 0.12,
  avgReliability: 0.89,
};

const mockTrendData = [0.08, 0.09, 0.11, 0.1, 0.09, 0.12, 0.14, 0.12, 0.11, 0.13, 0.15, 0.12];
const mockReliabilityTrend = [0.91, 0.89, 0.88, 0.9, 0.91, 0.89, 0.87, 0.89, 0.9, 0.88, 0.89, 0.89];

const mockRecentEvaluations = [
  {
    id: "eval-8834",
    correlationId: "invoice-8834",
    decision: "MATCH" as const,
    drift: 0.04,
    reliability: 0.92,
    template: "INV-ACME-001",
    timestamp: "2 min ago",
  },
  {
    id: "eval-9921",
    correlationId: "receipt-9921",
    decision: "REVIEW" as const,
    drift: 0.34,
    reliability: 0.71,
    template: "RCP-VENDOR-02",
    timestamp: "5 min ago",
  },
  {
    id: "eval-1234",
    correlationId: "contract-123",
    decision: "NEW" as const,
    drift: 0.89,
    reliability: 0.45,
    template: null,
    timestamp: "8 min ago",
  },
  {
    id: "eval-5567",
    correlationId: "invoice-5567",
    decision: "MATCH" as const,
    drift: 0.06,
    reliability: 0.94,
    template: "INV-ACME-001",
    timestamp: "12 min ago",
  },
  {
    id: "eval-7788",
    correlationId: "receipt-7788",
    decision: "REJECT" as const,
    drift: 0.78,
    reliability: 0.23,
    template: "RCP-OLD-01",
    timestamp: "15 min ago",
  },
];

const mockTemplates = [
  { id: "INV-ACME-001", name: "ACME Invoices", status: "ACTIVE", evaluations: 4521, avgDrift: 0.08 },
  { id: "RCP-VENDOR-02", name: "Vendor Receipts", status: "ACTIVE", evaluations: 2134, avgDrift: 0.15 },
  { id: "CON-LEGAL-01", name: "Legal Contracts", status: "REVIEW", evaluations: 892, avgDrift: 0.31 },
];

function StatCard({
  label,
  value,
  subValue,
  trend,
  animated = true,
  decimals = 0,
  suffix = "",
}: {
  label: string;
  value: number;
  subValue?: string;
  trend?: number[];
  animated?: boolean;
  decimals?: number;
  suffix?: string;
}) {
  return (
    <Box>
      <div className="text-terminal-white-dim text-sm mb-1">{label}</div>
      <div className="text-2xl text-terminal-green mb-1">
        {animated ? (
          <AnimatedCounter
            value={value}
            decimals={decimals}
            suffix={suffix}
            duration={1200}
          />
        ) : (
          value
        )}
      </div>
      {subValue && <div className="text-terminal-white-dim text-xs">{subValue}</div>}
      {trend && (
        <div className="mt-2">
          <Sparkline data={trend} animated />
        </div>
      )}
    </Box>
  );
}

function DecisionBreakdown() {
  const decisions = [
    { label: "MATCH", count: 973, color: "text-terminal-green" },
    { label: "REVIEW", count: 198, color: "text-terminal-amber" },
    { label: "NEW", count: 52, color: "text-terminal-cyan" },
    { label: "REJECT", count: 24, color: "text-terminal-red" },
  ];

  const total = decisions.reduce((sum, d) => sum + d.count, 0);

  return (
    <Box title="DECISION BREAKDOWN">
      <div className="space-y-3">
        {decisions.map((d, index) => (
          <div key={d.label} className="flex items-center gap-3">
            <span className={`w-16 text-sm ${d.color}`}>{d.label}</span>
            <div className="flex-1">
              <Progress
                value={(d.count / total) * 100}
                showPercent={false}
                animated
                delay={index * 150}
              />
            </div>
            <span className="text-terminal-white-dim text-sm w-12 text-right">
              <AnimatedCounter value={d.count} delay={index * 150} />
            </span>
          </div>
        ))}
      </div>
    </Box>
  );
}

function DriftTrendChart() {
  return (
    <Box title="DRIFT TREND (7 DAYS)">
      <div className="h-32 flex items-end justify-between gap-1">
        {mockTrendData.map((value, i) => (
          <div
            key={i}
            className="flex-1 bg-terminal-green animate-bar-rise"
            style={{
              height: `${(value / 0.2) * 100}%`,
              minHeight: "4px",
              animationDelay: `${i * 50}ms`,
            }}
          />
        ))}
      </div>
      <div className="flex justify-between mt-2 text-xs text-terminal-white-dim">
        <span>7d ago</span>
        <span>Today</span>
      </div>
    </Box>
  );
}

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      {/* Header with animated status */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl text-terminal-white">
            <TypewriterText text="Dashboard Overview" speed={30} cursor={false} />
          </h1>
          <p className="text-terminal-white-dim text-sm">
            Real-time monitoring of your document extraction pipeline
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-terminal-green">STATUS:</span>
          <PulseGlow color="green" intensity="low">
            <span className="text-terminal-green">All systems operational</span>
          </PulseGlow>
        </div>
      </div>

      {/* Hero visualization and stats */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Document visualization */}
        <div className="lg:col-span-1">
          <Box title="LIVE PROCESSING">
            <ASCIIDocumentViz autoPlay cycleDuration={8000} />
          </Box>
        </div>

        {/* Stats Grid */}
        <div className="lg:col-span-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="EVALUATIONS TODAY"
            value={mockStats.evaluationsToday}
            subValue={`${mockStats.evaluationsWeek.toLocaleString()} this week`}
          />
          <StatCard
            label="MATCH RATE"
            value={mockStats.matchRate}
            suffix="%"
            trend={[72, 74, 75, 73, 76, 78, 77, 79, 78, 76, 78, 78]}
          />
          <StatCard
            label="AVG DRIFT SCORE"
            value={mockStats.avgDrift}
            decimals={2}
            subValue="Target: < 0.15"
            trend={mockTrendData}
          />
          <StatCard
            label="AVG RELIABILITY"
            value={mockStats.avgReliability}
            decimals={2}
            subValue="Target: > 0.80"
            trend={mockReliabilityTrend}
          />
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <DecisionBreakdown />
        <DriftTrendChart />
      </div>

      {/* Tables Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Box title="RECENT EVALUATIONS">
          <Table
            columns={[
              { key: "correlationId", header: "ID" },
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
                header: "Rel.",
                render: (row) => row.reliability.toFixed(2),
              },
              { key: "timestamp", header: "Time" },
            ]}
            data={mockRecentEvaluations}
          />
        </Box>

        <Box title="TOP TEMPLATES">
          <Table
            columns={[
              { key: "id", header: "Template" },
              {
                key: "status",
                header: "Status",
                render: (row) => (
                  <StatusBadge
                    status={row.status as "ACTIVE" | "REVIEW"}
                  />
                ),
              },
              {
                key: "evaluations",
                header: "Evals",
                render: (row) => row.evaluations.toLocaleString(),
              },
              {
                key: "avgDrift",
                header: "Avg Drift",
                render: (row) => row.avgDrift.toFixed(2),
              },
            ]}
            data={mockTemplates}
          />
        </Box>
      </div>

      {/* Quick Actions */}
      <Box title="QUICK ACTIONS">
        <div className="flex flex-wrap gap-4">
          <a
            href="/dashboard/api-keys"
            className="text-terminal-green hover:underline hover:ascii-glow transition-all"
          >
            [+] Create API Key
          </a>
          <a
            href="/dashboard/templates"
            className="text-terminal-green hover:underline hover:ascii-glow transition-all"
          >
            [#] Manage Templates
          </a>
          <a
            href="/dashboard/evaluations"
            className="text-terminal-green hover:underline hover:ascii-glow transition-all"
          >
            [&gt;] View All Evaluations
          </a>
          <a href="/docs" className="text-terminal-green hover:underline hover:ascii-glow transition-all">
            [?] Documentation
          </a>
        </div>
      </Box>
    </div>
  );
}
